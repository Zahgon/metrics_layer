from metrics_layer.core.exceptions import QueryError
from metrics_layer.core.model.definitions import Definitions
from metrics_layer.core.sql.query_cumulative_metric import CumulativeMetricsQuery
from metrics_layer.core.sql.query_design import MetricsLayerDesign
from metrics_layer.core.sql.query_funnel import FunnelQuery
from metrics_layer.core.sql.query_generator import MetricsLayerQuery
from metrics_layer.core.utils import flatten_filters


class SingleSQLQueryResolver:
    def __init__(
        self,
        metrics: list,
        dimensions: list = [],
        funnel: dict = {},
        where: str = None,  # Either a list of json or a string
        having: str = None,  # Either a list of json or a string
        order_by: str = None,  # Either a list of json or a string
        topic=None,
        model=None,
        project=None,
        **kwargs,
    ):
        self.field_lookup = {}
        self.no_group_by = False
        self.has_cumulative_metric = False
        self.verbose = kwargs.get("verbose", False)
        self.select_raw_sql = kwargs.get("select_raw_sql", [])
        self.suppress_warnings = kwargs.get("suppress_warnings", False)
        self.limit = kwargs.get("limit")
        self.return_pypika_query = kwargs.get("return_pypika_query")
        self.force_group_by = kwargs.get("force_group_by", False)
        self.project = project
        self.metrics = metrics
        self.dimensions = dimensions
        self.funnel, self.is_funnel_query = self.parse_funnel(funnel)
        self.topic = topic
        self.model = model
        self.parse_field_names(where, having, order_by)
        self.nesting_depth = kwargs.get("nesting_depth", 0)
        self.query_type = kwargs.get("query_type")
        if self.query_type is None:
            raise QueryError(
                "Could not determine query_type. Please have connection information for "
                "your warehouse in the configuration or explicitly pass the "
                "'query_type' argument to this function"
            )
        self.parse_input()

    def get_query(self, semicolon: bool = True):
        pass

    def get_used_views(self):
        pass

    def parse_where(self, where: list):
        pass

    def parse_having(self, having: list):
        pass

    def parse_input(self):
        pass

    def get_field_with_error_handling(self, field_name: str, error_prefix: str):
        pass

    def parse_field_names(self, where, having, order_by):
        pass

    def parse_funnel(self, funnel: dict):
        pass

    @staticmethod
    def _is_literal(clause):
        pass

    def parse_identifiers_from_dicts(self, conditions: list):
        pass

    @staticmethod
    def flatten_filters(filters: list, return_nesting_depth: bool = False):
        return flatten_filters(filters, return_nesting_depth=return_nesting_depth)

    @staticmethod
    def _check_for_dict(conditions: list):
        pass
