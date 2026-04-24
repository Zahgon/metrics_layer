from collections import defaultdict

from pypika import AliasedQuery, Criterion, Order
from pypika.terms import LiteralValue

from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.model.field import Field
from metrics_layer.core.model.filter import LiteralValueCriterion
from metrics_layer.core.sql.query_base import MetricsLayerQueryBase
from metrics_layer.core.sql.query_dialect import (
    NullSorting,
    if_null_lookup,
    query_lookup,
)


class MetricsLayerMergedResultsQuery(MetricsLayerQueryBase):
    """ """

    def __init__(self, definition: dict) -> None:
        self.query_lookup = query_lookup
        super().__init__(definition)

    def get_query(self, semicolon: bool = True):
        # Build the base_cte table from the referenced queries + join them with all dimensions
        pass

    def build_cte_from(self):
        pass

    def _build_join_criteria(self, first_query_alias, second_query_alias, no_dimensions: bool):
        # No dimensions to join on, the query results must be just one number each
        pass

    # Code to handle SELECT portion of query
    def get_select_columns(self):
        pass

    def _apply_timestamp_casting(self, sql: str, field: Field):
        pass

    @staticmethod
    def nested_if_null(aliases, if_null_func):
        pass
