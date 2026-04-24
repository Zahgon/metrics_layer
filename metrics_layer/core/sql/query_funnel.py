import functools
from copy import deepcopy

from pypika import Criterion, JoinType, Table

from metrics_layer.core.exceptions import (
    AccessDeniedOrDoesNotExistException,
    QueryError,
)
from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.model.field import Field
from metrics_layer.core.model.filter import FilterInterval, LiteralValueCriterion
from metrics_layer.core.sql.query_base import MetricsLayerQueryBase
from metrics_layer.core.sql.query_design import MetricsLayerDesign
from metrics_layer.core.sql.query_dialect import query_lookup
from metrics_layer.core.sql.query_filter import MetricsLayerFilter
from metrics_layer.core.sql.query_generator import MetricsLayerQuery


class FunnelQuery(MetricsLayerQueryBase):
    """ """

    def __init__(self, definition: dict, design: MetricsLayerDesign, suppress_warnings: bool = False) -> None:
        self.design = design
        self.query_type = self.design.query_type
        self.no_group_by = self.design.no_group_by
        self.query_lookup = query_lookup
        self.suppress_warnings = suppress_warnings

        self.step_1_time = "step_1_time"
        self.result_cte_name = "result_cte"
        self.base_cte_name = design.base_cte_name
        super().__init__(definition)

    def __hash__(self):
        return hash(self.design.project)

    def get_query(self, semicolon: bool = True, cte_only: bool = False):
        pass

    def get_select_and_group_by(self, step_number: int):
        pass

    @functools.lru_cache(maxsize=None)
    def _get_base_select(self):
        pass

    def _get_step_select(self, step_number: int):
        pass

    def get_step_1_cte(self, from_query, base_table):
        pass

    def get_step_n_cte(self, from_query, base_table, previous_step_number: int):
        pass

    def get_funnel_base(self):
        pass

    def _get_event_condition_fields(self):
        pass

    def _get_fields_from_condition(self, condition):
        pass

    def get_event_date(self):
        pass

    @staticmethod
    def _cte(step_number: int):
        pass

    def where_for_event(self, step: list, step_number: int, event_date_alias: str):
        pass

    def _within_where(self, event_date_alias: str, step_number: int):
        pass

    def _subquery(self, metrics: list, dimensions: list, where: list, no_group_by: bool):
        pass

    def _enrich_query_design(self, metrics: list, dimensions: list):
        pass

    def join_graphs_for_query(self, metrics, dimensions, where):
        pass
