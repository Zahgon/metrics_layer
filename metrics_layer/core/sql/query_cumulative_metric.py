import functools
from copy import deepcopy

from pypika import Criterion, JoinType, Table

from metrics_layer.core.exceptions import AccessDeniedOrDoesNotExistException
from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.model.filter import LiteralValueCriterion
from metrics_layer.core.sql.query_base import MetricsLayerQueryBase
from metrics_layer.core.sql.query_design import MetricsLayerDesign
from metrics_layer.core.sql.query_dialect import query_lookup
from metrics_layer.core.sql.query_filter import MetricsLayerFilter
from metrics_layer.core.sql.query_generator import MetricsLayerQuery

SNOWFLAKE_DATE_SPINE = (
    "select dateadd(day, seq4(), '2000-01-01') as date from table(generator(rowcount => 365*40))"
)
BIGQUERY_DATE_SPINE = "select date from unnest(generate_date_array('2000-01-01', '2040-01-01')) as date"
POSTGRES_DATE_SPINE = (
    "select date from generate_series('2000-01-01'::date, '2040-01-01'::date, '1 day') as date"
)


class CumulativeMetricsQuery(MetricsLayerQueryBase):
    """ """

    def __init__(self, definition: dict, design: MetricsLayerDesign, suppress_warnings: bool = False) -> None:
        self.design = design
        self.query_type = self.design.query_type
        self.no_group_by = self.design.no_group_by
        self.query_lookup = query_lookup
        self.suppress_warnings = suppress_warnings

        self.date_spine_cte_name = design.date_spine_cte_name
        self.base_cte_name = design.base_cte_name

        self._default_date_memo = {}
        super().__init__(definition)

    def __hash__(self):
        return hash(self.design.project)

    def get_query(self, semicolon: bool = True):
        pass

    def separate_metrics(self):
        pass

    @staticmethod
    def date_spine(query_type: str):
        pass

    def date_spine_by_time_frame(self):
        pass

    def cumulative_subquery(self, cumulative_metric):
        pass

    def non_cumulative_subquery(self):
        pass

    def _subquery(self, metrics: list, dimensions: list, where: list, no_group_by: bool):
        pass

    def aggregate_cumulative_subquery(self, cumulative_metric):
        pass

    def _is_default_date(self, field):
        pass

    @functools.lru_cache(maxsize=None)
    def default_date_dimension_group(self):
        pass

    def _replace_cumulative_where(self, cumulative_metric, date_spine_reference: str):
        pass

    def _cumulative_where_fields(self, cumulative_metric, refs_only=False):
        pass

    def _get_default_date(self, field, cumulative_metric):
        pass

    def _derive_join(self, cumulative_metric, base_table: Table):
        pass

    def _get_select_columns(self, base_table: Table):
        pass

    @property
    def current_date(self):
        pass
