from copy import deepcopy
from typing import List, Union

from metrics_layer.core.exceptions import (
    AccessDeniedOrDoesNotExistException,
    JoinError,
    QueryError,
)
from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.model.project import Project
from metrics_layer.core.sql.query_arbitrary_merged_queries import (
    MetricsLayerMergedQueries,
)
from metrics_layer.core.sql.query_base import QueryKindTypes
from metrics_layer.core.sql.resolve import SQLQueryResolver
from metrics_layer.core.sql.single_query_resolve import SingleSQLQueryResolver


class ArbitraryMergedQueryResolver(SingleSQLQueryResolver):
    def __init__(
        self,
        merged_queries: List[dict],
        where: List[dict] = [],
        having: List[dict] = [],
        order_by: List[dict] = [],
        project: Union[Project, None] = None,
        connections: List = [],
        **kwargs,
    ):
        merged_queries = self.validate_arbitrary_merged_queries(merged_queries)
        self.merged_queries = merged_queries
        self.verbose = kwargs.get("verbose", False)
        self.where = where
        self.having = having
        self.order_by = order_by
        self.limit = kwargs.pop("limit", None)
        self.project = project
        self.connections = connections
        self.connection = None
        self.model = None
        # All queries are merged queries (obviously)
        self.query_kind = QueryKindTypes.merged
        self.kwargs = kwargs
        self._mapping_lookup = {}

    @property
    def mapping_lookup(self):
        pass

    def get_query(self, semicolon: bool = True):
        pass

    def _resolve_join_fields_mappings(
        self,
        primary_resolver: SQLQueryResolver,
        secondary_resolver: SQLQueryResolver,
        join_fields: List[dict],
        query_number: int,
    ):
        pass

    # Note: this mutates join_field
    def _resolve_join_logic(self, resolver, key, join_field, query_number: int):
        pass

    def _raise_join_error(self, field_name: str, query_number):
        raise JoinError(
            f"Join field {field_name} not found in the query number {query_number}. To be used as a join the"
            f" field must be included in query {query_number}."
        )

    def _init_resolver(self, merged_query: dict, extra_lookup_dims: list = []):
        pass

    def _add_mapping_lookup(self, resolver: SQLQueryResolver):
        pass

    @staticmethod
    def validate_arbitrary_merged_queries(merged_queries: list):
        pass
