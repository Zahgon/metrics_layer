import hashlib
import json
from collections import defaultdict
from copy import deepcopy

from metrics_layer.core.exceptions import QueryError
from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.sql.query_merged_results import MetricsLayerMergedResultsQuery
from metrics_layer.core.sql.single_query_resolve import SingleSQLQueryResolver


class MergedSQLQueryResolver(SingleSQLQueryResolver):
    def __init__(
        self,
        metrics: list,
        dimensions: list = [],
        funnel: dict = {},
        where: str = None,  # Either a list of json or a string
        having: str = None,  # Either a list of json or a string
        order_by: str = None,  # Either a list of json or a string
        model=None,
        project=None,
        **kwargs,
    ):
        if funnel != {}:
            raise QueryError("Funnel queries are not supported in merged results queries")

        self.field_lookup = {}
        self.no_group_by = False
        self.has_cumulative_metric = False
        self.verbose = kwargs.get("verbose", False)
        self.select_raw_sql = kwargs.get("select_raw_sql", [])
        self.suppress_warnings = kwargs.get("suppress_warnings", False)
        self.limit = kwargs.get("limit")
        self.return_pypika_query = kwargs.get("return_pypika_query")
        self.force_group_by = kwargs.get("force_group_by", False)
        self.kwargs = kwargs
        self.project = project
        self.metrics = metrics
        self.dimensions = dimensions
        self.model = model
        self.parse_field_names(where, having, order_by)
        self.query_type = None

    def get_query(self, semicolon: bool = True):
        pass

    def derive_sub_queries(self, topic=None):
        pass

    def _parse_where_filter(self, where_filter, dimension_mapping, join_hash):
        pass

    def _resolve_where_mapped_filter(self, where_filter_object, dimension_mapping, join_hash):
        pass

    def _canon_date_mapping(self):
        pass

    def _join_hash_key(self, field):
        # This makes the join hash out of all the joinable graphs, it's crucial to use this when
        # naming the CTEs so in subsequent checks we can match up all joinable fields,
        # not just fields in the same view.

        # Here we're checking if the field is a measure, if so we need to get the canon date
        # to calculate the join hash. This solves the issue where the canon date has a different
        # join hash from its associated metric. In that case we use the canon date's join hash.
        pass

    def _join_hash_contains_join_graph(self, join_hash: str, join_graphs: list):
        # Due to situations like subquery_1 and subquery_12 we have to split these
        # apart and check if any of the join graphs are in the split list
        pass

    @staticmethod
    def _cte_name_from_parts(field_id: str, join_group_hash: str):
        pass

    @staticmethod
    def deduplicate_fields(field_dict: dict):
        # Get rid of duplicates while keeping order to make joining work properly
        pass

    @staticmethod
    def hash_dict(input_dict: dict):
        pass
