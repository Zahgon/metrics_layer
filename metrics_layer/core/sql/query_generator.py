from copy import copy
from typing import Dict, List, Union

from pypika import Criterion, Order, Table
from pypika.terms import LiteralValue

from metrics_layer.core.exceptions import QueryError
from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.model.field import Field
from metrics_layer.core.model.filter import LiteralValueCriterion
from metrics_layer.core.model.view import View
from metrics_layer.core.sql.query_base import MetricsLayerQueryBase
from metrics_layer.core.sql.query_design import MetricsLayerDesign
from metrics_layer.core.sql.query_dialect import NullSorting, query_lookup
from metrics_layer.core.sql.query_errors import ArgumentError
from metrics_layer.core.sql.query_filter import MetricsLayerFilter
from metrics_layer.core.utils import flatten_filters


class MetricsLayerQuery(MetricsLayerQueryBase):
    """ """

    def __init__(self, definition: Dict, design: MetricsLayerDesign, suppress_warnings: bool = False) -> None:
        # The Design this Query has been built for
        self.design = design
        self.query_type = self.design.query_type
        self.no_group_by = self.design.no_group_by
        self.query_lookup = query_lookup
        self.suppress_warnings = suppress_warnings

        # A collection of all the column and aggregate filters in the query + order by
        self.where_filters = []
        self.having_filters = []
        self.having_group_by_filters = []
        self.funnel_filters = []
        self.order_by_args = []
        # This flag controls if we interpolate the whole window function or just the window function name
        # The former case is for building the cte to reference later on
        # The latter case is for building the final query
        self.render_window_functions = definition.get("render_window_functions", False)
        self.parse_definition(definition)

        super().__init__(definition)

    def parse_definition(self, definition: dict):
        # Parse and store the provided filters
        pass

    def _parse_filter_object(
        self, filter_object, filter_type: str, access_filter: Union[str, None] = None, nesting_depth: int = 0
    ):
        pass

    def _parse_order_by_object(self, order_by):
        pass

    def needs_join(self):
        pass

    def get_query(self, semicolon: bool = True, view_overrides: dict = {}):
        pass

    # Code to handle SELECT portion of query
    def get_select_columns(self):
        pass

    def _get_group_by_select_columns(self):
        pass

    def _get_no_group_by_select_columns(self):
        pass

    def _sql_from_field_no_group_by(self, field: Field) -> List:
        pass

    def _deduplicate_select(self, select_with_duplicates: list):
        pass

    # Code to handle the FROM portion of the query
    def get_join_query_from(self, base_join_query, view_overrides: dict):
        # Base table from statement
        pass

    def get_single_table_query_from(self, base_query, view_overrides: dict):
        pass

    def _table_expression(self, view: View, override_cte_reference: Union[str, None] = None):
        # Create a pypika Table based on the Table's name or it's derived table sql definition
        pass

    def _window_function_cte(self, cte: dict):
        pass

    def _non_additive_cte(self, definition: dict, group_by_dimensions: list, view_overrides: dict = {}):
        pass

    # Code for the GROUP BY part of the query
    def get_group_by_columns(self):
        pass

    # Code for formatting values
    def get_sql(self, field, alias: Union[None, str] = None, use_symmetric: bool = False):
        pass
