import json
from collections import defaultdict
from copy import copy
from itertools import combinations, product

import networkx

from metrics_layer.core.exceptions import (
    AccessDeniedOrDoesNotExistException,
    QueryError,
)
from metrics_layer.core.model.definitions import Definitions

from .base import SQLReplacement
from .join import Join, ZenlyticJoinRelationship, ZenlyticJoinType


class IdentifierTypes:
    primary = "primary"
    foreign = "foreign"
    join = "join"

    options = [primary, foreign, join]


class JoinGraph(SQLReplacement):
    def __init__(self, project) -> None:
        self.project = project
        self._join_preference = [
            ZenlyticJoinRelationship.one_to_one,
            ZenlyticJoinRelationship.many_to_one,
            ZenlyticJoinRelationship.one_to_many,
            ZenlyticJoinRelationship.many_to_many,
        ]
        self._merged_result_graph = None
        self._graph = None
        self._field_memo = {}
        self._weak_graph_memo = {}
        self._strong_graph_memo = {}

    def subgraph(self, view_names: list):
        return self.graph.subgraph(view_names)

    @property
    def graph(self):
        pass

    def list_join_graphs(self):
        graph = self.project.join_graph.graph
        sorted_components = self._strongly_connected_components(graph)
        return [f"subquery_{i}" for i, _ in enumerate(sorted_components)]

    def join_graph_hash(self, view_name: str) -> str:
        if view_name not in self._strong_graph_memo:
            graph = self.project.join_graph.graph
            sorted_components = self._strongly_connected_components(graph)

            sorted_comps = enumerate(sorted_components)
            graph_hash = next((f"subquery_{i}" for i, comps in sorted_comps if view_name in comps), None)
            if graph_hash is None:
                raise QueryError(
                    f"View name {view_name} not found in any joinable part of your data model. "
                    "Please make sure this is the right name for the view."
                )

            self._strong_graph_memo[view_name] = graph_hash
        return self._strong_graph_memo[view_name]

    def weak_join_graph_hashes(self, view_name: str) -> list:
        if view_name not in self._weak_graph_memo:
            graph = self.project.join_graph.graph
            sorted_components = self._strongly_connected_components(graph)

            join_graph_hashes = []
            for i, components in enumerate(sorted_components):
                subgraph_nodes = self._subgraph_nodes_from_components(graph, components)
                if view_name in subgraph_nodes:
                    join_graph_hashes.append(f"subquery_{i}")

            self._weak_graph_memo[view_name] = join_graph_hashes
        return self._weak_graph_memo[view_name]

    def get_joinable_view_names(self, view_name: str):
        graph = self.project.join_graph.graph
        sorted_components = self._strongly_connected_components(graph)

        joinable_views = []
        for components in sorted_components:
            subgraph_nodes = self._subgraph_nodes_from_components(graph, components)
            if view_name in subgraph_nodes:
                joinable_views.extend(list(subgraph_nodes))

        return [v for v in sorted(list(set(joinable_views))) if v != view_name]

    def _strongly_connected_components(self, graph):
        components = networkx.strongly_connected_components(graph)
        # Sort the sub-components graphs alphabetically
        sorted_sub_components = [list(sorted(c)) for c in components]
        # Sort by largest component, then inverse alphabetically based on the first view name
        sorted_components = sorted(sorted_sub_components, key=lambda x: (len(x), x[0]), reverse=True)
        return sorted_components

    @staticmethod
    def _subgraph_nodes_from_components(graph, components):
        edges = networkx.edge_dfs(graph, source=components)
        all_edges = list(edges) + [list(components)]
        return list(set(node for edge in all_edges for node in edge))

    def ordered_joins(self, view_pairs: list):
        joins = []
        joined_views = []
        for base_view, join_view in view_pairs:
            # A view joining to itself with the same logic is not a valid join
            if base_view != join_view:
                join = self.get_join(base_view, join_view)
                if join_view not in joined_views:
                    joins.append(join)
                joined_views.append(join_view)
        return joins

    def collect_errors(self):
        errors = []
        for join in self.joins():
            errors.extend(join.collect_errors())
        return errors

    def joins(self):
        joins = []
        for base_view_name, join_view_name in self.graph.edges():
            joins.append(self.get_join(base_view_name, join_view_name))
        return joins

    def get_join(self, base_view_name: str, join_view_name: str):
        join_info = self.graph[base_view_name][join_view_name]
        join_definition = {**join_info, "base_view_name": base_view_name, "join_view_name": join_view_name}
        return Join(join_definition, project=self.project)

    def build(self):
        pass

    def merged_results_graph(self, model):
        if self._merged_result_graph is None:
            self._merged_result_graph = self._build_merged_results_graph(model)
        return self._merged_result_graph

    def _build_merged_results_graph(self, model):
        with_dates = [
            field
            for field in self.project.fields(model_name=model.name)
            if field.canon_date and field.field_type == "measure"
        ]
        mappings = model.get_mappings(dimensions_only=True)

        # Merged result shared date and field mapping
        graph = networkx.DiGraph()

        existing_root_nodes, join_group_hashes = self._add_canon_dates_to_merged_result(
            graph, with_dates, join_root=Definitions.canon_date_join_graph_root
        )
        self._add_mappings_to_merged_result(
            graph,
            mappings,
            must_exist_in=list(join_group_hashes),
            root_nodes=existing_root_nodes,
            measures_only=True,
        )

        ordered_hashes = sorted(list(join_group_hashes))
        for join_group_hash_1, join_group_hash_2 in combinations(ordered_hashes, 2):
            join_root = join_group_hash_1 + "_" + join_group_hash_2

            pair = [join_group_hash_1, join_group_hash_2]
            existing_sub_root_nodes, _ = self._add_canon_dates_to_merged_result(
                graph, with_dates, join_root, use_condition=True, must_be_in=pair
            )

            # Add any fields that accessible via a join to both join_group_hash_1 and join_group_hash_2
            for view in self.project.views(model_name=model.name):
                join_hashes = self.project.join_graph.weak_join_graph_hashes(view.name)
                if all(join_hash in join_hashes for join_hash in pair):
                    view_fields = self.project.fields(
                        view_name=view.name, model_name=model.name, expand_dimension_groups=True
                    )
                    for field in view_fields:
                        for node in existing_sub_root_nodes:
                            graph.add_edge(node, field.id())

            self._add_mappings_to_merged_result(
                graph, mappings, must_exist_in=pair, root_nodes=existing_sub_root_nodes
            )

        return graph

    def _add_canon_dates_to_merged_result(
        self, graph, measures: list, join_root: str, use_condition: bool = False, must_be_in: list = []
    ):
        self._field_memo = {}
        existing_root_nodes, join_group_hashes = set(), set()
        for measure in measures:
            join_hash = self.project.join_graph.join_graph_hash(measure.view.name)
            join_group_hashes.add(join_hash)
            if not use_condition or (use_condition and join_hash in must_be_in):
                measure_id = measure.id()
                try:
                    canon_date = self._get_field_with_memo(measure.canon_date, by_name=True)
                    for timeframe in canon_date.timeframes:
                        canon_date.dimension_group = timeframe
                        root_node_name = join_root + "_" + timeframe
                        graph.add_edges_from(
                            [(root_node_name, canon_date.id()), (root_node_name, measure_id)]
                        )
                        existing_root_nodes.add(root_node_name)
                except AccessDeniedOrDoesNotExistException:
                    # In the event that the canon_date doesn't exist anymore, don't break everything
                    pass
        return sorted(list(existing_root_nodes)), join_group_hashes

    def _add_mappings_to_merged_result(
        self, graph, mappings: dict, must_exist_in: list, root_nodes: list, measures_only: bool = False
    ):
        for from_field, mapping in mappings.items():
            if mapping.get("is_canon_date_mapping"):
                continue
            if measures_only and mapping["field_type"] != "measure":
                continue
            for reference in mapping["references"]:
                to_field = reference["field"]
                if mapping["from_join_hash"] in must_exist_in and reference["to_join_hash"] in must_exist_in:
                    from_ = self._get_field_with_memo(from_field).id()
                    to_ = self._get_field_with_memo(to_field).id()
                    for node in root_nodes:
                        graph.add_edges_from([(node, from_), (node, to_)])

    def _get_field_with_memo(self, field_name: str, by_name: bool = False):
        if field_name not in self._field_memo:
            if by_name:
                field = self.project.get_field_by_name(field_name)
            else:
                field = self.project.get_field(field_name)
            self._field_memo[field_name] = field
        else:
            field = self._field_memo[field_name]
        return field

    def _identifier_map(self):
        pass

    def _composite_keys(self, primary_key_map: dict):
        pass

    def _reference_map(self):
        pass

    def _identifier_to_join(self, first_identifier, first_view_name, second_identifier, second_view_name):
        pass

    def _identifier_join_clause(self, identifier: dict, view_name: str):
        pass

    def _verify_identifier_join(self, join: dict):
        pass

    @staticmethod
    def _derive_relationship(identifier, join_identifier):
        pass

    @staticmethod
    def _invert_relationship(relationship: str):
        pass

    @staticmethod
    def _edge_weight(relationship: str):
        pass

    @staticmethod
    def _allowed_join(only_join: list, view_name: str):
        pass

    @staticmethod
    def _is_fanout(relationship: str):
        pass
