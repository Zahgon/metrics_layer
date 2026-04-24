from pypika import AliasedQuery, Criterion, Order
from pypika.terms import LiteralValue

from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.model.filter import LiteralValueCriterion
from metrics_layer.core.model.join import ZenlyticJoinType
from metrics_layer.core.sql.query_base import MetricsLayerQueryBase
from metrics_layer.core.sql.query_dialect import NullSorting, query_lookup


class MetricsLayerMergedQueries(MetricsLayerQueryBase):
    """Resolve the SQL query for multiple, arbitrary merged queries"""

    def __init__(self, definition: dict) -> None:
        self.query_lookup = query_lookup
        super().__init__(definition)

    def get_query(self, semicolon: bool = True):
        # Build the base_cte table from the referenced queries + join them with all dimensions
        pass

    def build_cte_from(self):
        pass

    def _build_join_criteria(self, join_logic: list, base_query_alias: str, joined_query_alias: str):
        # Join logic is a list with {'field': field_in_current_cte, 'source_field': field_in_base_cte}
        # No dimensions to join on, the query results must be just one number each
        pass

    # Code to handle SELECT portion of query
    def get_select_columns(self):
        pass
