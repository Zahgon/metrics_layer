from collections import Counter, defaultdict
from copy import deepcopy
from typing import List, Union

from metrics_layer.core.exceptions import JoinError, QueryError
from metrics_layer.core.model.filter import Filter, MetricsLayerFilterExpressionType
from metrics_layer.core.model.project import Project
from metrics_layer.core.sql.merged_query_resolve import MergedSQLQueryResolver
from metrics_layer.core.sql.query_base import QueryKindTypes
from metrics_layer.core.sql.single_query_resolve import SingleSQLQueryResolver


class SQLQueryResolver(SingleSQLQueryResolver):
    def __init__(
        self,
        metrics: list,
        dimensions: list = [],
        funnel: dict = {},  # A dict with steps (list) and within (dict)
        where: Union[str, None, List] = None,  # Either a list of json or a string
        having: Union[str, None, List] = None,  # Either a list of json or a string
        order_by: Union[str, None, List] = None,  # Either a list of json or a string
        project: Union[Project, None] = None,
        connections: List = [],
        **kwargs,
    ):
        self.field_lookup = {}
        self.no_group_by = False
        self.mapping_forces_merged_result = False
        self.verbose = kwargs.get("verbose", False)
        self.select_raw_sql = kwargs.get("select_raw_sql", [])
        self.suppress_warnings = kwargs.get("suppress_warnings", False)
        self.limit = kwargs.get("limit")
        self.single_query = kwargs.get("single_query", False)
        self.kwargs = kwargs
        self.project = project
        if self.kwargs.get("topic"):
            self.topic = self.project.get_topic(kwargs["topic"])
            self.kwargs["topic"] = self.topic
        else:
            self.topic = None
        self.model = self._get_model_for_query(kwargs.get("model_name"), metrics, dimensions)
        self.connections = connections
        self.metrics = metrics
        self.dimensions = dimensions
        self.funnel = funnel
        self.where = where if where else []
        always_where = self._apply_always_filter(metrics + dimensions)
        if always_where:
            self.where.extend(always_where)
        self.where = self._clean_conditional_filter_syntax(self.where)
        self.having = self._clean_conditional_filter_syntax(having)
        self.order_by = order_by
        self.connection = self._get_connection(self.model.connection)
        self.kwargs["query_type"] = self._get_query_type(self.connection, self.kwargs)
        connection_schema = self._get_connection_schema(self.connection)
        self.project.set_connection_schema(connection_schema)
        self.field_id_mapping = {}
        self._resolve_mapped_fields()
        self.query_type = None

    @property
    def is_merged_result(self):
        pass

    def get_query(self, semicolon: bool = True):
        pass

    def _get_single_query(self, semicolon: bool):
        pass

    def _get_merged_result_query(self, semicolon: bool):
        pass

    def _resolve_mapped_fields(self):
        pass

    def _replace_field_value_in_group_by_filter(self):
        pass

    def _get_field_from_lookup(self, field_name: str, only_search_lookup: bool = False):
        pass

    def determine_field_to_replace_with(self, mapped_field, joinable_graphs, mergeable_graphs):
        pass

    def _join_graphs_by_type(self, field_lookup: dict):
        pass

    def _handle_invalid_merged_result(self, mergeable_graphs, joinable_graphs):
        # If both of these are empty there is no join overlap and the query cannot be run
        pass

    def _replace_mapped_field(self, to_replace: str, field):
        pass

    def _replace_dict_or_literal(self, where, to_replace, field):
        pass

    def _get_model_for_query(self, model_name: str = None, metrics: list = [], dimensions: list = []):
        pass

    def _derive_model(self, metrics: list, dimensions: list):
        pass

    def _get_query_type(self, connection, kwargs: dict):
        pass

    def _apply_always_filter(self, fields: list):
        pass

    @staticmethod
    def _deduplicate_always_where_filters(filters: list):
        pass

    def _clean_conditional_filter_syntax(self, filters: Union[str, None, List]):
        pass

    def _get_connection_schema(self, connection):
        pass

    def _get_connection(self, connection_name: str):
        pass
