import functools
import hashlib
import json
import re
from copy import copy
from typing import TYPE_CHECKING, Any, List, Union

import sqlglot
from pypika.terms import LiteralValue
from sqlglot import expressions as exp

from metrics_layer.core.exceptions import (
    AccessDeniedOrDoesNotExistException,
    MetricsLayerException,
    QueryError,
)
from metrics_layer.core.utils import compute_combined_sql_md5

from .base import MetricsLayerBase, SQLReplacement
from .definitions import Definitions, sql_flavor_to_sqlglot_format
from .filter import Filter
from .set import Set

SQL_KEYWORDS = {"order", "group", "by", "as", "from", "select", "on", "with", "drop", "table"}
VALID_TIMEFRAMES = [
    "raw",
    "time",
    "second",
    "minute",
    "hour",
    "date",
    "week",
    "month",
    "quarter",
    "year",
    "fiscal_month",
    "fiscal_quarter",
    "fiscal_year",
    "week_index",
    "week_of_year",
    "week_of_month",
    "month_of_year",
    "month_of_year_full_name",
    "month_of_year_index",
    "fiscal_month_index",
    "fiscal_month_of_year_index",
    "month_name",
    "month_index",
    "quarter_of_year",
    "fiscal_quarter_of_year",
    "hour_of_day",
    "day_of_week",
    "day_of_month",
    "day_of_year",
]
VALID_INTERVALS = [
    "second",
    "minute",
    "hour",
    "day",
    "week",
    "month",
    "quarter",
    "year",
]
VALID_VALUE_FORMAT_NAMES = [
    "decimal",
    "decimal_0",
    "decimal_1",
    "decimal_2",
    "decimal_3",
    "decimal_4",
    "decimal_pct_0",
    "decimal_pct_1",
    "decimal_pct_2",
    "decimal_pct_3",
    "decimal_pct_4",
    "percent_0",
    "percent_1",
    "percent_2",
    "percent_3",
    "percent_4",
    "eur",
    "eur_0",
    "eur_1",
    "eur_2",
    "usd",
    "usd_0",
    "usd_1",
    "usd_2",
    "string",
    "image_from_url",
    "date",
    "week",
    "month",
    "quarter",
    "year",
]
if TYPE_CHECKING:
    from metrics_layer.core.model.view import View


class ZenlyticFieldType:
    dimension = "dimension"
    dimension_group = "dimension_group"
    measure = "measure"
    options = [dimension, dimension_group, measure]


class ZenlyticDataType:
    timestamp = "timestamp"
    date = "date"
    datetime = "datetime"
    default = timestamp
    options = [timestamp, date, datetime]


class ZenlyticType:
    count = "count"
    count_distinct = "count_distinct"
    sum = "sum"
    sum_distinct = "sum_distinct"
    average = "average"
    average_distinct = "average_distinct"
    median = "median"
    percentile = "percentile"
    max = "max"
    min = "min"
    number = "number"
    yesno = "yesno"
    tier = "tier"
    string = "string"
    time = "time"
    duration = "duration"
    cumulative = "cumulative"
    dimension_options = [string, yesno, number, tier, time]
    dimension_group_options = [time, duration]
    measure_options = [
        count,
        count_distinct,
        sum,
        sum_distinct,
        average,
        average_distinct,
        median,
        max,
        min,
        number,
        cumulative,
        string,
        yesno,
        time,
        percentile,
    ]
    numeric_measure_options = [
        count,
        count_distinct,
        sum,
        sum_distinct,
        average,
        average_distinct,
        median,
        max,
        min,
        number,
        cumulative,
    ]
    non_aggregating_measure_options = [number, string, yesno, time]
    requires_sql_distinct_key = [sum_distinct, average_distinct]
    options = list(sorted(list(set(dimension_options + dimension_group_options + measure_options))))


class Field(MetricsLayerBase, SQLReplacement):
    shared_properties = (
        "name",
        "field_type",
        "type",
        "datatype",
        "label",
        "group_label",
        "description",
        "zoe_description",
        "hidden",
        "value_format_name",
        "synonyms",
        "required_access_grants",
        "label_prefix",
        "filters",
        "sql",
        "extra",
        "window",
    )
    internal_properties = ("is_dynamic_field", "promotable", "parent_sql_query")

    def __init__(self, definition: dict, view) -> None:
        self.defaults = {"type": "string", "primary_key": False, "datatype": "timestamp"}
        self.default_intervals = ["second", "minute", "hour", "day", "week", "month", "quarter", "year"]

        # Always lowercase names and make exception for the None case in the
        # event of this being used by a filter and not having a name.
        if "name" in definition and isinstance(definition["name"], str):
            definition["name"] = definition["name"].lower()

        # Remove the label prefix if it's null
        if "label_prefix" in definition and definition["label_prefix"] is None:
            definition.pop("label_prefix")

        if "promotable" not in definition:
            definition["promotable"] = True

        self.view: View = view
        self.validate(definition)
        super().__init__(definition)

    def __hash__(self) -> int:
        result = hashlib.md5(self.id().encode("utf-8"))
        id_int = int(result.hexdigest(), base=16)
        return hash(self.view.project) + id_int

    def __eq__(self, other):
        if isinstance(other, str):
            return False
        return self.id() == other.id()

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.id()}>"

    def id(self, capitalize_alias=False):
        pass

    @property
    def valid_properties(self):
        pass

    @property
    def hidden(self):
        pass

    @property
    def result_type(self):
        pass

    @property
    def sql(self):
        pass

    @property
    def sql_start(self):
        pass

    @property
    def sql_end(self):
        pass

    @property
    def label(self):
        pass

    @property
    def field_type(self) -> str:
        pass

    @property
    def measure(self):
        pass

    @property
    def timeframes(self):
        pass

    @property
    def filters(self):
        pass

    @property
    def convert_timezone(self):
        pass

    @property
    def datatype(self):
        pass

    @property
    def is_merged_result(self):
        pass

    def combined_sql_md5(self) -> str:
        pass

    def sql_hash(self):
        # The query type doesn't matter for generating the hash
        pass

    def sql_replacement_func(self, sql: str):
        pass

    def loses_join_ability_with_other_views(self):
        if "is_merged_result" in self._definition:
            return self._definition["is_merged_result"]
        elif self.type == "number" and self.field_type == ZenlyticFieldType.measure:
            # For number types, if the references have different canon_date views
            # then we need to make it not joinable
            referenced_canon_date_views = list()
            for reference in self.referenced_fields(self.sql):
                if (
                    not isinstance(reference, str)
                    and reference.field_type == ZenlyticFieldType.measure
                    and reference.type != "cumulative"
                ):
                    if reference.canon_date:
                        canon_date_view_name, _ = reference.canon_date.split(".")
                        weak_hashes = self.view.project.join_graph.weak_join_graph_hashes(
                            canon_date_view_name
                        )
                        referenced_canon_date_views.append(set(weak_hashes))

            # Check that all the referenced view sets are the same
            if referenced_canon_date_views:
                return any(s != referenced_canon_date_views[0] for s in referenced_canon_date_views)

        return False

    @property
    def canon_date(self):
        pass

    @property
    def drill_fields(self):
        pass

    @property
    def non_additive_dimension(self):
        pass

    @property
    def update_where_timeframe(self):
        # if this value is present we use it, otherwise we default to True
        pass

    def cte_prefix(self, aggregated: bool = True):
        if self.type == "cumulative":
            prefix = "aggregated" if aggregated else "subquery"
            return f"{prefix}_{self.alias(with_view=True)}"
        return

    def alias(self, with_view: bool = False):
        if self.field_type == ZenlyticFieldType.dimension_group:
            if self.type == "time":
                alias = f"{self.name}_{self.dimension_group}"
            elif self.type == "duration":
                alias = f"{self.dimension_group}_{self.name}"
            else:
                alias = self.name
        else:
            alias = self.name
        if with_view:
            return f"{self.view.name}_{alias}"
        return alias

    def sql_query(
        self,
        query_type: Union[str, None] = None,
        functional_pk: Union[str, None] = None,
        alias_only: bool = False,
        render_window_functions: bool = False,
        model_format: bool = False,
    ):
        if not query_type:
            query_type = self._derive_query_type()
        if model_format and self._field_uses_non_standard_model_format_sql():
            # If the field uses non-standard model format for SQL, that implies its sql
            # is logically impossible to render as-is to the model due to dependencies higher up.
            # We need to return a UDF which the model can use and we can re-reference as needed.
            return f"{self.view.name}.{self.name}()"
        elif model_format:
            render_window_functions = True
            wrapping_func = self.ensure_column_reference_exists
        else:
            wrapping_func = self.default_wrapping_func

        if self.type == "cumulative" and alias_only:
            return f"{self.cte_prefix()}.{self.measure.alias(with_view=True)}"
        if self.field_type == ZenlyticFieldType.measure:
            return wrapping_func(
                self.aggregate_sql_query(
                    query_type, functional_pk, alias_only=alias_only, model_format=model_format
                ),
                query_type=query_type,
            )
        return wrapping_func(
            self.raw_sql_query(
                query_type,
                alias_only=alias_only,
                render_window_functions=render_window_functions,
            ),
            query_type=query_type,
        )

    def default_wrapping_func(self, sql, query_type: str):
        pass

    def _field_uses_non_standard_model_format_sql(self):
        if self.field_type == ZenlyticFieldType.measure and self.non_additive_dimension:
            return True
        return False

    def ensure_column_reference_exists(self, sql, query_type: str) -> str:
        pass

    def raw_sql_query(
        self,
        query_type: str,
        alias_only: bool = False,
        render_window_functions: bool = False,
    ):
        if (
            self.field_type == ZenlyticFieldType.measure
            and self.type in ZenlyticType.non_aggregating_measure_options
        ):
            return self.get_referenced_sql_query()
        elif alias_only:
            return self.alias(with_view=True)
        elif not render_window_functions and self.window:
            return self.alias(with_view=True)
        return self.get_replaced_sql_query(
            query_type, alias_only=alias_only, render_window_functions=render_window_functions
        )

    def aggregate_sql_query(
        self, query_type: str, functional_pk: str, alias_only: bool = False, model_format: bool = False
    ):
        sql = self.raw_sql_query(query_type, alias_only=alias_only)
        type_lookup = {
            ZenlyticType.sum: self._sum_aggregate_sql,
            ZenlyticType.sum_distinct: self._sum_distinct_aggregate_sql,
            ZenlyticType.count: self._count_aggregate_sql,
            ZenlyticType.count_distinct: self._count_distinct_aggregate_sql,
            ZenlyticType.average: self._average_aggregate_sql,
            ZenlyticType.average_distinct: self._average_distinct_aggregate_sql,
            ZenlyticType.median: self._median_aggregate_sql,
            ZenlyticType.percentile: self._percentile_aggregate_sql,
            ZenlyticType.max: self._max_aggregate_sql,
            ZenlyticType.min: self._min_aggregate_sql,
            ZenlyticType.number: self._non_aggregating_measure_sql,
            ZenlyticType.string: self._non_aggregating_measure_sql,
            ZenlyticType.yesno: self._non_aggregating_measure_sql,
            ZenlyticType.time: self._non_aggregating_measure_sql,
        }
        if self.type not in type_lookup:
            raise QueryError(
                f"Aggregate type {self.type} not supported. Supported types are: {list(type_lookup.keys())}"
            )
        return type_lookup[self.type](sql, query_type, functional_pk, alias_only, model_format)

    def strict_replaced_query(self):
        pass

    def _needs_symmetric_aggregate(self, functional_pk: MetricsLayerBase):
        pass

    def _get_sql_distinct_key(self, sql_distinct_key: str, query_type: str, alias_only: bool):
        pass

    def _count_distinct_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _sum_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _sum_distinct_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _sum_symmetric_aggregate(
        self,
        sql: str,
        query_type: str,
        primary_key_sql: str = None,
        alias_only: bool = False,
        factor: int = 1_000_000,
    ):
        pass

    def _sum_symmetric_aggregate_bigquery(
        self, sql: str, primary_key_sql: str, alias_only: bool, factor: int = 1_000_000
    ):
        pass

    def _sum_symmetric_aggregate_postgres(
        self, sql: str, primary_key_sql: str, alias_only: bool, factor: int = 1_000_000
    ):
        pass

    def _sum_symmetric_aggregate_redshift(
        self, sql: str, primary_key_sql: str, alias_only: bool, factor: int = 1_000_000
    ):
        pass

    def _sum_symmetric_aggregate_snowflake(
        self, sql: str, primary_key_sql: str, alias_only: bool, factor: int = 1_000_000
    ):
        pass

    def _sum_symmetric_aggregate_azure_synapse(
        self, sql: str, primary_key_sql: str, alias_only: bool, factor: int = 1_000_000
    ):
        pass

    def _count_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _count_symmetric_aggregate(
        self,
        sql: str,
        query_type: str,
        primary_key_sql: str = None,
        alias_only: bool = False,
        factor: int = 1_000_000,
    ):
        # This works for both all types
        pass

    def _count_symmetric_aggregate_snowflake(
        self, sql: str, query_type: str, primary_key_sql: str, alias_only: bool
    ):
        pass

    def _average_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _average_distinct_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _average_symmetric_aggregate(
        self, sql: str, query_type, primary_key_sql: str = None, alias_only: bool = False
    ):
        pass

    def _median_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _percentile_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def _max_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        # Max works natively with symmetric aggregates, so there's just the one return
        pass

    def _min_aggregate_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        # Min works natively with symmetric aggregates, so there's just the one return
        pass

    def _non_aggregating_measure_sql(
        self, sql: str, query_type: str, functional_pk: str, alias_only: bool, model_format: bool = False
    ):
        pass

    def required_views(self):
        views = []
        if self.sql:
            views.extend(self._get_required_views_from_sql(self.sql))
        elif self.sql_start and self.sql_end:
            views.extend(self._get_required_views_from_sql(self.sql_start))
            views.extend(self._get_required_views_from_sql(self.sql_end))
        else:
            # There is not sql or sql_start or sql_end, it must be a
            # default count measure which references only the field's base view
            pass

        return list(set([self.view.name] + views))

    def _get_required_views_from_sql(self, sql: str):
        views = []
        for field_name in self.fields_to_replace(sql):
            if field_name != "TABLE":
                field = self.get_field_with_view_info(field_name)
                views.extend(field.required_views())
        return views

    def validate(self, definition: dict):
        required_keys = ["name", "field_type"]
        for k in required_keys:
            if k not in definition:
                name_str = ""
                if "name" in definition:
                    name_str = f" '{definition['name']}'"
                raise QueryError(
                    f"Field{name_str} missing required key '{k}' The field passed was {definition} in the"
                    f" view {self.view.name}"
                )

    def to_dict(self, query_type: str = None):
        output = {**self._definition}
        output["sql_raw"] = copy(self.sql)
        if (
            output["field_type"] == ZenlyticFieldType.measure
            and output["type"] in ZenlyticType.non_aggregating_measure_options
        ):
            output["sql"] = self.get_referenced_sql_query()
        elif output["field_type"] == ZenlyticFieldType.dimension_group and self.dimension_group is None:
            output["sql"] = copy(self.sql)
        elif query_type:
            output["sql"] = self.sql_query(query_type)
        return output

    def to_yaml_properties_format(self):
        pass

    def printable_attributes(self):
        to_print = [
            "name",
            "field_type",
            "type",
            "label",
            "group_label",
            "hidden",
            "primary_key",
            "timeframes",
            "datatype",
            "sql",
        ]
        attributes = self.to_dict()
        return {key: attributes.get(key) for key in to_print if attributes.get(key) is not None}

    def equal(self, field_name: str):
        # Determine if the field name passed in references this field
        view_name, field_name_only = self.field_name_parts(field_name)
        if view_name and view_name != self.view.name:
            return False

        if self.field_type == ZenlyticFieldType.dimension_group and self.dimension_group is None:
            if field_name_only in self.dimension_group_names():
                self.dimension_group = self.get_dimension_group_name(field_name_only)
                return True
            return False
        elif self.field_type == ZenlyticFieldType.dimension_group:
            return self.alias() == field_name_only
        return self.name == field_name_only

    def dimension_group_names(self):
        if self.field_type == ZenlyticFieldType.dimension_group and self.type == "time":
            return [f"{self.name}_{t}" for t in self.timeframes]
        if self.field_type == ZenlyticFieldType.dimension_group and self.type == "duration":
            return [f"{t}s_{self.name}" for t in self._definition.get("intervals", self.default_intervals)]
        return []

    def get_dimension_group_name(self, field_name: str):
        if self.type == "duration" and f"_{self.name}" in field_name:
            return field_name.replace(f"_{self.name}", "")
        if self.type == "time":
            return field_name.replace(f"{self.name}_", "")
        return None

    def apply_dimension_group_duration_sql(self, sql_start: str, sql_end: str, query_type: str):
        return self.dimension_group_duration_sql(sql_start, sql_end, query_type, self.dimension_group)

    @staticmethod
    def dimension_group_duration_sql(sql_start: str, sql_end: str, query_type: str, dimension_group: str):
        meta_lookup = {
            Definitions.snowflake: {
                "seconds": lambda start, end: f"DATEDIFF('SECOND', {start}, {end})",
                "minutes": lambda start, end: f"DATEDIFF('MINUTE', {start}, {end})",
                "hours": lambda start, end: f"DATEDIFF('HOUR', {start}, {end})",
                "days": lambda start, end: f"DATEDIFF('DAY', {start}, {end})",
                "weeks": lambda start, end: f"DATEDIFF('WEEK', {start}, {end})",
                "months": lambda start, end: f"DATEDIFF('MONTH', {start}, {end})",
                "quarters": lambda start, end: f"DATEDIFF('QUARTER', {start}, {end})",
                "years": lambda start, end: f"DATEDIFF('YEAR', {start}, {end})",
            },
            Definitions.trino: {
                "seconds": lambda start, end: f"DATE_DIFF('SECOND', {start}, {end})",
                "minutes": lambda start, end: f"DATE_DIFF('MINUTE', {start}, {end})",
                "hours": lambda start, end: f"DATE_DIFF('HOUR', {start}, {end})",
                "days": lambda start, end: f"DATE_DIFF('DAY', {start}, {end})",
                "weeks": lambda start, end: f"DATE_DIFF('WEEK', {start}, {end})",
                "months": lambda start, end: f"DATE_DIFF('MONTH', {start}, {end})",
                "quarters": lambda start, end: f"DATE_DIFF('QUARTER', {start}, {end})",
                "years": lambda start, end: f"DATE_DIFF('YEAR', {start}, {end})",
            },
            Definitions.mysql: {
                "seconds": lambda start, end: f"TIMESTAMPDIFF(SECOND, {start}, {end})",
                "minutes": lambda start, end: f"TIMESTAMPDIFF(MINUTE, {start}, {end})",
                "hours": lambda start, end: f"TIMESTAMPDIFF(HOUR, {start}, {end})",
                "days": lambda start, end: f"TIMESTAMPDIFF(DAY, {start}, {end})",
                "weeks": lambda start, end: f"TIMESTAMPDIFF(WEEK, {start}, {end})",
                "months": lambda start, end: f"TIMESTAMPDIFF(MONTH, {start}, {end})",
                "quarters": lambda start, end: f"TIMESTAMPDIFF(QUARTER, {start}, {end})",
                "years": lambda start, end: f"TIMESTAMPDIFF(YEAR, {start}, {end})",
            },
            Definitions.postgres: {
                "seconds": lambda start, end: (  # noqa
                    f"{meta_lookup[Definitions.postgres]['minutes'](start, end)} * 60 + DATE_PART('SECOND',"
                    f" AGE({end}, {start}))"
                ),
                "minutes": lambda start, end: (  # noqa
                    f"{meta_lookup[Definitions.postgres]['hours'](start, end)} * 60 + DATE_PART('MINUTE',"
                    f" AGE({end}, {start}))"
                ),
                "hours": lambda start, end: (  # noqa
                    f"{meta_lookup[Definitions.postgres]['days'](start, end)} * 24 + DATE_PART('HOUR',"
                    f" AGE({end}, {start}))"
                ),
                "days": lambda start, end: f"DATE_PART('DAY', AGE({end}, {start}))",
                "weeks": lambda start, end: f"TRUNC(DATE_PART('DAY', AGE({end}, {start}))/7)",
                "months": lambda start, end: (  # noqa
                    f"{meta_lookup[Definitions.postgres]['years'](start, end)} * 12 + (DATE_PART('month',"
                    f" AGE({end}, {start})))"
                ),
                "quarters": lambda start, end: (  # noqa
                    f"{meta_lookup[Definitions.postgres]['years'](start, end)} * 4 + TRUNC(DATE_PART('month',"
                    f" AGE({end}, {start}))/3)"
                ),
                "years": lambda start, end: f"DATE_PART('YEAR', AGE({end}, {start}))",
            },
            Definitions.druid: {
                "seconds": lambda start, end: f"TIMESTAMPDIFF(SECOND, {start}, {end})",
                "minutes": lambda start, end: f"TIMESTAMPDIFF(MINUTE, {start}, {end})",
                "hours": lambda start, end: f"TIMESTAMPDIFF(HOUR, {start}, {end})",
                "days": lambda start, end: f"TIMESTAMPDIFF(DAY, {start}, {end})",
                "weeks": lambda start, end: f"TIMESTAMPDIFF(WEEK, {start}, {end})",
                "months": lambda start, end: f"TIMESTAMPDIFF(MONTH, {start}, {end})",
                "quarters": lambda start, end: f"TIMESTAMPDIFF(QUARTER, {start}, {end})",
                "years": lambda start, end: f"TIMESTAMPDIFF(YEAR, {start}, {end})",
            },
            Definitions.sql_server: {
                "seconds": lambda start, end: f"DATEDIFF(SECOND, {start}, {end})",
                "minutes": lambda start, end: f"DATEDIFF(MINUTE, {start}, {end})",
                "hours": lambda start, end: f"DATEDIFF(HOUR, {start}, {end})",
                "days": lambda start, end: f"DATEDIFF(DAY, {start}, {end})",
                "weeks": lambda start, end: f"DATEDIFF(WEEK, {start}, {end})",
                "months": lambda start, end: f"DATEDIFF(MONTH, {start}, {end})",
                "quarters": lambda start, end: f"DATEDIFF(QUARTER, {start}, {end})",
                "years": lambda start, end: f"DATEDIFF(YEAR, {start}, {end})",
            },
            Definitions.bigquery: {
                "seconds": lambda start, end: (  # noqa
                    f"TIMESTAMP_DIFF(CAST({end} as TIMESTAMP), CAST({start} as TIMESTAMP), SECOND)"
                ),
                "minutes": lambda start, end: (  # noqa
                    f"TIMESTAMP_DIFF(CAST({end} as TIMESTAMP), CAST({start} as TIMESTAMP), MINUTE)"
                ),
                "hours": lambda start, end: (  # noqa
                    f"TIMESTAMP_DIFF(CAST({end} as TIMESTAMP), CAST({start} as TIMESTAMP), HOUR)"
                ),
                "days": lambda start, end: f"DATE_DIFF(CAST({end} as DATE), CAST({start} as DATE), DAY)",
                "weeks": lambda start, end: f"DATE_DIFF(CAST({end} as DATE), CAST({start} as DATE), ISOWEEK)",
                "months": lambda start, end: f"DATE_DIFF(CAST({end} as DATE), CAST({start} as DATE), MONTH)",
                "quarters": lambda start, end: (  # noqa
                    f"DATE_DIFF(CAST({end} as DATE), CAST({start} as DATE), QUARTER)"
                ),
                "years": lambda start, end: f"DATE_DIFF(CAST({end} as DATE), CAST({start} as DATE), ISOYEAR)",
            },
        }
        meta_lookup[Definitions.teradata] = {
            "seconds": lambda start, end: (
                f"(CAST({end} AS DATE) - CAST({start} AS DATE)) * 86400"
                f" + EXTRACT(HOUR FROM (CAST({end} AS TIMESTAMP(0)) - CAST({start} AS TIMESTAMP(0))"
                f" HOUR(4) TO SECOND)) * 3600"
                f" + EXTRACT(MINUTE FROM (CAST({end} AS TIMESTAMP(0)) - CAST({start} AS TIMESTAMP(0))"
                f" HOUR(4) TO SECOND)) * 60"
                f" + EXTRACT(SECOND FROM (CAST({end} AS TIMESTAMP(0)) - CAST({start} AS TIMESTAMP(0))"
                f" HOUR(4) TO SECOND))"
            ),
            "minutes": lambda start, end: (
                f"(CAST({end} AS DATE) - CAST({start} AS DATE)) * 1440"
                f" + EXTRACT(HOUR FROM (CAST({end} AS TIMESTAMP(0)) - CAST({start} AS TIMESTAMP(0))"
                f" HOUR(4) TO SECOND)) * 60"
                f" + EXTRACT(MINUTE FROM (CAST({end} AS TIMESTAMP(0)) - CAST({start} AS TIMESTAMP(0))"
                f" HOUR(4) TO SECOND))"
            ),
            "hours": lambda start, end: (
                f"(CAST({end} AS DATE) - CAST({start} AS DATE)) * 24"
                f" + EXTRACT(HOUR FROM (CAST({end} AS TIMESTAMP(0)) - CAST({start} AS TIMESTAMP(0))"
                f" HOUR(4) TO SECOND))"
            ),
            "days": lambda start, end: f"(CAST({end} AS DATE) - CAST({start} AS DATE))",
            "weeks": lambda start, end: f"(CAST({end} AS DATE) - CAST({start} AS DATE)) / 7",
            "months": lambda start, end: (
                f"(EXTRACT(YEAR FROM CAST({end} AS DATE)) - EXTRACT(YEAR FROM CAST({start} AS DATE))) * 12"
                f" + (EXTRACT(MONTH FROM CAST({end} AS DATE)) - EXTRACT(MONTH FROM CAST({start} AS DATE)))"
            ),
            "quarters": lambda start, end: (
                f"((EXTRACT(YEAR FROM CAST({end} AS DATE)) - EXTRACT(YEAR FROM CAST({start} AS DATE))) * 12"
                f" + (EXTRACT(MONTH FROM CAST({end} AS DATE))"
                f" - EXTRACT(MONTH FROM CAST({start} AS DATE)))) / 3"
            ),
            "years": lambda start, end: (
                f"EXTRACT(YEAR FROM CAST({end} AS DATE)) - EXTRACT(YEAR FROM CAST({start} AS DATE))"
            ),
        }
        # SQL Server and Databricks have identical syntax in this case
        meta_lookup[Definitions.databricks] = meta_lookup[Definitions.sql_server]
        # Snowflake and redshift have identical syntax in this case
        meta_lookup[Definitions.redshift] = meta_lookup[Definitions.snowflake]
        # Snowflake and duck db have identical syntax in this case
        meta_lookup[Definitions.duck_db] = meta_lookup[Definitions.snowflake]
        # Azure Synapse and SQL Server have identical syntax
        meta_lookup[Definitions.azure_synapse] = meta_lookup[Definitions.sql_server]
        # Athena and Trino have identical syntax
        meta_lookup[Definitions.athena] = meta_lookup[Definitions.trino]
        try:
            return meta_lookup[query_type][dimension_group](sql_start, sql_end)
        except KeyError:
            raise QueryError(
                f"Unable to find a valid method for running {dimension_group} with query type {query_type}"
            )

    def apply_dimension_group_time_sql(self, sql: str, query_type: str):
        meta_lookup = {
            Definitions.snowflake: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
                "second": lambda s, qt: f"DATE_TRUNC('SECOND', {s})",
                "minute": lambda s, qt: f"DATE_TRUNC('MINUTE', {s})",
                "hour": lambda s, qt: f"DATE_TRUNC('HOUR', {s})",
                "date": lambda s, qt: f"DATE_TRUNC('DAY', {s})",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATE_TRUNC('MONTH', {s})",
                "quarter": lambda s, qt: f"CONCAT(EXTRACT(YEAR FROM {s}), '-Q', EXTRACT(QUARTER FROM {s}))",
                "year": lambda s, qt: f"DATE_TRUNC('YEAR', {s})",
                "fiscal_month": lambda s, qt: (
                    f"DATE_TRUNC('MONTH', {self._fiscal_offset_to_timestamp(s, qt)})"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(EXTRACT(YEAR FROM {self._fiscal_offset_to_timestamp(s, qt)}), '-Q',"
                    f" EXTRACT(QUARTER FROM {self._fiscal_offset_to_timestamp(s, qt)}))"
                ),
                "fiscal_year": lambda s, qt: f"DATE_TRUNC('YEAR', {self._fiscal_offset_to_timestamp(s, qt)})",
                "week_index": lambda s, qt: (
                    f"EXTRACT(WEEK FROM {self._apply_week_start_day_offset_only(s, qt)})"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(WEEK FROM {s}) - EXTRACT(WEEK FROM DATE_TRUNC('MONTH', {s})) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM {s})",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM {self._fiscal_offset_to_timestamp(s, qt)})"
                ),
                "month_of_year": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Mon')",
                "month_of_year_full_name": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'MMMM')",
                "quarter_of_year": lambda s, qt: f"EXTRACT(QUARTER FROM {s})",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"EXTRACT(QUARTER FROM {self._fiscal_offset_to_timestamp(s, qt)})"
                ),
                "hour_of_day": lambda s, qt: f"EXTRACT(HOUR FROM CAST({s} AS TIMESTAMP))",
                "day_of_week": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Dy')",
                "day_of_month": lambda s, qt: f"EXTRACT(DAY FROM {s})",
                "day_of_year": lambda s, qt: f"EXTRACT(DOY FROM {s})",
            },
            Definitions.databricks: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
                "second": lambda s, qt: f"DATE_TRUNC('SECOND', CAST({s} AS TIMESTAMP))",
                "minute": lambda s, qt: f"DATE_TRUNC('MINUTE', CAST({s} AS TIMESTAMP))",
                "hour": lambda s, qt: f"DATE_TRUNC('HOUR', CAST({s} AS TIMESTAMP))",
                "date": lambda s, qt: f"DATE_TRUNC('DAY', CAST({s} AS TIMESTAMP))",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATE_TRUNC('MONTH', CAST({s} AS TIMESTAMP))",
                "quarter": (
                    lambda s, qt: f"CONCAT(EXTRACT(YEAR FROM CAST({s} AS TIMESTAMP)), '-Q', EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP)))"
                ),  # noqa
                "year": lambda s, qt: f"DATE_TRUNC('YEAR', CAST({s} AS TIMESTAMP))",
                "fiscal_month": lambda s, qt: (
                    f"DATE_TRUNC('MONTH', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(EXTRACT(YEAR FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP)),"
                    f" '-Q', EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " TIMESTAMP)))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"DATE_TRUNC('YEAR', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "week_index": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({self._apply_week_start_day_offset_only(s, qt)} AS TIMESTAMP))"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({s} AS TIMESTAMP)) - EXTRACT(WEEK FROM DATE_TRUNC('MONTH',"
                    f" CAST({s} AS TIMESTAMP))) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP))",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "month_of_year": lambda s, qt: f"DATE_FORMAT(CAST({s} AS TIMESTAMP), 'MMM')",
                "month_of_year_full_name": lambda s, qt: f"DATE_FORMAT(CAST({s} AS TIMESTAMP), 'MMMM')",
                "quarter_of_year": lambda s, qt: f"EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP))",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "hour_of_day": lambda s, qt: f"EXTRACT(HOUR FROM CAST({s} AS TIMESTAMP))",
                "day_of_week": lambda s, qt: f"DATE_FORMAT(CAST({s} AS TIMESTAMP), 'E')",
                "day_of_month": lambda s, qt: f"EXTRACT(DAY FROM CAST({s} AS TIMESTAMP))",
                "day_of_year": lambda s, qt: f"EXTRACT(DOY FROM CAST({s} AS TIMESTAMP))",
            },
            Definitions.postgres: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
                "second": lambda s, qt: f"DATE_TRUNC('SECOND', CAST({s} AS TIMESTAMP))",
                "minute": lambda s, qt: f"DATE_TRUNC('MINUTE', CAST({s} AS TIMESTAMP))",
                "hour": lambda s, qt: f"DATE_TRUNC('HOUR', CAST({s} AS TIMESTAMP))",
                "date": lambda s, qt: f"DATE_TRUNC('DAY', CAST({s} AS TIMESTAMP))",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATE_TRUNC('MONTH', CAST({s} AS TIMESTAMP))",
                "quarter": (
                    lambda s, qt: f"CONCAT(EXTRACT(YEAR FROM CAST({s} AS TIMESTAMP)), '-Q', EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP)))"
                ),  # noqa
                "year": lambda s, qt: f"DATE_TRUNC('YEAR', CAST({s} AS TIMESTAMP))",
                "fiscal_month": lambda s, qt: (
                    f"DATE_TRUNC('MONTH', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(EXTRACT(YEAR FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP)),"
                    f" '-Q', EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " TIMESTAMP)))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"DATE_TRUNC('YEAR', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "week_index": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({self._apply_week_start_day_offset_only(s, qt)} AS TIMESTAMP))"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({s} AS TIMESTAMP)) - EXTRACT(WEEK FROM DATE_TRUNC('MONTH',"
                    f" CAST({s} AS TIMESTAMP))) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP))",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "month_of_year": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Mon')",
                "month_of_year_full_name": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Month')",
                "quarter_of_year": lambda s, qt: f"EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP))",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "hour_of_day": lambda s, qt: f"EXTRACT('HOUR' FROM CAST({s} AS TIMESTAMP))",
                "day_of_week": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Dy')",
                "day_of_month": lambda s, qt: f"EXTRACT('DAY' FROM CAST({s} AS TIMESTAMP))",
                "day_of_year": lambda s, qt: f"EXTRACT('DOY' FROM CAST({s} AS TIMESTAMP))",
            },
            Definitions.trino: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
                "second": lambda s, qt: f"DATE_TRUNC('SECOND', CAST({s} AS TIMESTAMP))",
                "minute": lambda s, qt: f"DATE_TRUNC('MINUTE', CAST({s} AS TIMESTAMP))",
                "hour": lambda s, qt: f"DATE_TRUNC('HOUR', CAST({s} AS TIMESTAMP))",
                "date": lambda s, qt: f"DATE_TRUNC('DAY', CAST({s} AS TIMESTAMP))",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATE_TRUNC('MONTH', CAST({s} AS TIMESTAMP))",
                "quarter": (
                    lambda s, qt: f"CONCAT(CAST(EXTRACT(YEAR FROM CAST({s} AS TIMESTAMP)) AS VARCHAR), '-Q', CAST(EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP)) AS VARCHAR))"
                ),  # noqa
                "year": lambda s, qt: f"DATE_TRUNC('YEAR', CAST({s} AS TIMESTAMP))",
                "fiscal_month": lambda s, qt: (
                    f"DATE_TRUNC('MONTH', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(CAST(EXTRACT(YEAR FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP)) AS VARCHAR),"
                    f" '-Q', CAST(EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " TIMESTAMP)) AS VARCHAR))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"DATE_TRUNC('YEAR', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "week_index": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({self._apply_week_start_day_offset_only(s,qt)} AS TIMESTAMP))"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({s} AS TIMESTAMP)) - EXTRACT(WEEK FROM DATE_TRUNC('MONTH',"
                    f" CAST({s} AS TIMESTAMP))) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP))",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "month_of_year": lambda s, qt: f"FORMAT_DATETIME(CAST({s} AS TIMESTAMP), 'MMM')",
                "month_of_year_full_name": lambda s, qt: f"FORMAT_DATETIME(CAST({s} AS TIMESTAMP), 'MMMM')",
                "quarter_of_year": lambda s, qt: f"EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP))",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "hour_of_day": lambda s, qt: f"EXTRACT(HOUR FROM CAST({s} AS TIMESTAMP))",
                "day_of_week": lambda s, qt: f"FORMAT_DATETIME(CAST({s} AS TIMESTAMP), 'EEE')",
                "day_of_month": lambda s, qt: f"EXTRACT(DAY FROM CAST({s} AS TIMESTAMP))",
                "day_of_year": lambda s, qt: f"EXTRACT(DOY FROM CAST({s} AS TIMESTAMP))",
            },
            Definitions.mysql: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS DATETIME)",
                "second": lambda s, qt: f"DATE_FORMAT({s}, '%Y-%m-%d %H:%i:%s')",
                "minute": lambda s, qt: f"DATE_FORMAT({s}, '%Y-%m-%d %H:%i:00')",
                "hour": lambda s, qt: f"DATE_FORMAT({s}, '%Y-%m-%d %H:00:00')",
                "date": lambda s, qt: f"DATE({s})",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATE_FORMAT({s}, '%Y-%m-01')",
                "quarter": lambda s, qt: f"CONCAT(YEAR({s}), '-Q', QUARTER({s}))",
                "year": lambda s, qt: f"DATE_FORMAT({s}, '%Y-01-01')",
                "fiscal_month": lambda s, qt: (
                    f"DATE_FORMAT({self._fiscal_offset_to_timestamp(s, qt)}, '%Y-%m-01')"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(YEAR({self._fiscal_offset_to_timestamp(s, qt)}), '-Q',"
                    f" QUARTER({self._fiscal_offset_to_timestamp(s, qt)}))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"DATE_FORMAT({self._fiscal_offset_to_timestamp(s, qt)}, '%Y-01-01')"
                ),
                "week_index": lambda s, qt: f"WEEK({self._apply_week_start_day_offset_only(s, qt)})",
                "week_of_month": lambda s, qt: f"WEEK({s}) - WEEK(DATE_FORMAT({s}, '%Y-%m-01')) + 1",
                "month_of_year_index": lambda s, qt: f"MONTH({s})",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"MONTH({self._fiscal_offset_to_timestamp(s, qt)})"
                ),
                "month_of_year": lambda s, qt: f"DATE_FORMAT({s}, '%b')",
                "month_of_year_full_name": lambda s, qt: f"DATE_FORMAT({s}, '%M')",
                "quarter_of_year": lambda s, qt: f"QUARTER({s})",
                "fiscal_quarter_of_year": lambda s, qt: f"QUARTER({self._fiscal_offset_to_timestamp(s, qt)})",
                "hour_of_day": lambda s, qt: f"HOUR({s})",
                "day_of_week": lambda s, qt: f"DATE_FORMAT({s}, '%a')",
                "day_of_month": lambda s, qt: f"DAY({s})",
                "day_of_year": lambda s, qt: f"DAYOFYEAR({s})",
            },
            Definitions.druid: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
                "second": lambda s, qt: f"DATE_TRUNC('SECOND', CAST({s} AS TIMESTAMP))",
                "minute": lambda s, qt: f"DATE_TRUNC('MINUTE', CAST({s} AS TIMESTAMP))",
                "hour": lambda s, qt: f"DATE_TRUNC('HOUR', CAST({s} AS TIMESTAMP))",
                "date": lambda s, qt: f"DATE_TRUNC('DAY', CAST({s} AS TIMESTAMP))",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATE_TRUNC('MONTH', CAST({s} AS TIMESTAMP))",
                "quarter": (
                    lambda s, qt: f"CONCAT(EXTRACT(YEAR FROM CAST({s} AS TIMESTAMP)), '-Q', EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP)))"
                ),  # noqa
                "year": lambda s, qt: f"DATE_TRUNC('YEAR', CAST({s} AS TIMESTAMP))",
                "fiscal_month": lambda s, qt: (
                    f"DATE_TRUNC('MONTH', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(EXTRACT(YEAR FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP)),"
                    f" '-Q', EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " TIMESTAMP)))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"DATE_TRUNC('YEAR', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "week_index": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({self._apply_week_start_day_offset_only(s,qt)} AS TIMESTAMP))"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({s} AS TIMESTAMP)) - EXTRACT(WEEK FROM DATE_TRUNC('MONTH',"
                    f" CAST({s} AS TIMESTAMP))) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP))",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "month_of_year": lambda s, qt: (  # noqa
                    f"CASE EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP)) WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb'"
                    " WHEN 3 THEN 'Mar' WHEN 4 THEN 'Apr' WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN"
                    " 'Jul' WHEN 8 THEN 'Aug' WHEN 9 THEN 'Sep' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' WHEN"
                    " 12 THEN 'Dec' ELSE 'Invalid Month' END"
                ),
                "month_of_year_full_name": lambda s, qt: (
                    f"CASE EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP)) WHEN 1 THEN 'January' WHEN 2 THEN "
                    "'February' WHEN 3 THEN 'March' WHEN 4 THEN 'April' WHEN 5 THEN 'May' WHEN 6 THEN "
                    "'June' WHEN 7 THEN 'July' WHEN 8 THEN 'August' WHEN 9 THEN 'September' WHEN 10 THEN "
                    "'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December' ELSE 'Invalid Month' END"
                ),
                "quarter_of_year": lambda s, qt: f"EXTRACT(QUARTER FROM CAST({s} AS TIMESTAMP))",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"EXTRACT(QUARTER FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                ),
                "hour_of_day": lambda s, qt: f"EXTRACT(HOUR FROM CAST({s} AS TIMESTAMP))",
                "day_of_week": lambda s, qt: (  # noqa
                    f"CASE EXTRACT(DOW FROM CAST({s} AS TIMESTAMP)) WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN"
                    " 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' WHEN 7 THEN 'Sun'"
                    " ELSE 'Invalid Day' END"
                ),
                "day_of_month": lambda s, qt: f"EXTRACT(DAY FROM CAST({s} AS TIMESTAMP))",
                "day_of_year": lambda s, qt: f"EXTRACT(DOY FROM CAST({s} AS TIMESTAMP))",
            },
            Definitions.sql_server: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS DATETIME)",
                "second": lambda s, qt: f"DATEADD(SECOND, DATEDIFF(SECOND, 0, CAST({s} AS DATETIME)), 0)",
                "minute": lambda s, qt: f"DATEADD(MINUTE, DATEDIFF(MINUTE, 0, CAST({s} AS DATETIME)), 0)",
                "hour": lambda s, qt: f"DATEADD(HOUR, DATEDIFF(HOUR, 0, CAST({s} AS DATETIME)), 0)",
                "date": lambda s, qt: f"CAST(CAST({s} AS DATE) AS DATETIME)",
                "week": self._week_dimension_group_time_sql,
                "month": lambda s, qt: f"DATEADD(MONTH, DATEDIFF(MONTH, 0, CAST({s} AS DATE)), 0)",
                "quarter": (
                    lambda s, qt: f"CONCAT(YEAR(CAST({s} AS DATE)), '-Q', DATEPART(QUARTER, CAST({s} AS DATE)))"
                ),
                "year": lambda s, qt: f"DATEADD(YEAR, DATEDIFF(YEAR, 0, CAST({s} AS DATE)), 0)",
                "fiscal_month": lambda s, qt: (
                    f"DATEADD(MONTH, DATEDIFF(MONTH, 0, CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " DATE)), 0)"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"CONCAT(YEAR(CAST({self._fiscal_offset_to_timestamp(s, qt)} AS DATE)), '-Q',"
                    f" DATEPART(QUARTER, CAST({self._fiscal_offset_to_timestamp(s, qt)} AS DATE)))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"DATEADD(YEAR, DATEDIFF(YEAR, 0, CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " DATE)), 0)"
                ),
                "week_index": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({self._apply_week_start_day_offset_only(s,qt)} AS DATE))"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(WEEK FROM CAST({s} AS DATE)) - EXTRACT(WEEK FROM DATEADD(MONTH, DATEDIFF(MONTH,"
                    f" 0, CAST({s} AS DATE)), 0)) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM CAST({s} AS DATE))",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS DATE))"
                ),
                "month_of_year": lambda s, qt: f"LEFT(DATENAME(MONTH, CAST({s} AS DATE)), 3)",
                "month_of_year_full_name": lambda s, qt: f"DATENAME(MONTH, CAST({s} AS DATE))",
                "quarter_of_year": lambda s, qt: f"DATEPART(QUARTER, CAST({s} AS DATE))",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"DATEPART(QUARTER, CAST({self._fiscal_offset_to_timestamp(s, qt)} AS DATE))"
                ),
                "hour_of_day": lambda s, qt: f"DATEPART(HOUR, CAST({s} AS DATETIME))",
                "day_of_week": lambda s, qt: f"LEFT(DATENAME(WEEKDAY, CAST({s} AS DATE)), 3)",
                "day_of_month": lambda s, qt: f"DATEPART(DAY, CAST({s} AS DATE))",
                "day_of_year": lambda s, qt: f"DATEPART(Y, CAST({s} AS DATE))",
            },
            Definitions.bigquery: {
                "raw": lambda s, qt: s,
                "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
                "second": lambda s, qt: (  # noqa
                    f"CAST(DATETIME_TRUNC(CAST({s} AS DATETIME), SECOND) AS {self.datatype.upper()})"
                ),
                "minute": lambda s, qt: (  # noqa
                    f"CAST(DATETIME_TRUNC(CAST({s} AS DATETIME), MINUTE) AS {self.datatype.upper()})"
                ),
                "hour": lambda s, qt: (  # noqa
                    f"CAST(DATETIME_TRUNC(CAST({s} AS DATETIME), HOUR) AS {self.datatype.upper()})"
                ),
                "date": lambda s, qt: f"CAST(DATE_TRUNC(CAST({s} AS DATE), DAY) AS {self.datatype.upper()})",
                "week": lambda s, qt: (
                    f"CAST({self._week_dimension_group_time_sql(s, qt)} AS {self.datatype.upper()})"
                ),
                "month": lambda s, qt: (  # noqa
                    f"CAST(DATE_TRUNC(CAST({s} AS DATE), MONTH) AS {self.datatype.upper()})"
                ),
                "quarter": (
                    lambda s, qt: f"FORMAT_TIMESTAMP('%Y-Q%Q', CAST({s} AS TIMESTAMP))"
                ),  # noqa  # noqa
                "year": lambda s, qt: f"CAST(DATE_TRUNC(CAST({s} AS DATE), YEAR) AS {self.datatype.upper()})",
                "fiscal_month": lambda s, qt: (
                    f"CAST(DATE_TRUNC(CAST({self._fiscal_offset_to_timestamp(s, qt)} AS DATE), MONTH) AS"
                    f" {self.datatype.upper()})"
                ),
                "fiscal_quarter": lambda s, qt: (
                    f"FORMAT_TIMESTAMP('%Y-Q%Q', CAST({self._fiscal_offset_to_timestamp(s, qt)} AS"
                    " TIMESTAMP))"
                ),
                "fiscal_year": lambda s, qt: (
                    f"CAST(DATE_TRUNC(CAST({self._fiscal_offset_to_timestamp(s, qt)} AS DATE), YEAR) AS"
                    f" {self.datatype.upper()})"
                ),
                "week_index": lambda s, qt: (
                    f"EXTRACT(ISOWEEK FROM {self._apply_week_start_day_offset_only(s,qt)})"
                ),
                "week_of_month": lambda s, qt: (
                    f"EXTRACT(ISOWEEK FROM {s}) - EXTRACT(ISOWEEK FROM DATE_TRUNC(CAST({s} AS DATE),"
                    " MONTH)) + 1"
                ),
                "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM {s})",
                "fiscal_month_of_year_index": lambda s, qt: (
                    f"EXTRACT(MONTH FROM {self._fiscal_offset_to_timestamp(s, qt)})"
                ),
                "month_of_year": lambda s, qt: f"LEFT(FORMAT_DATETIME('%B', CAST({s} as DATETIME)), 3)",
                "month_of_year_full_name": lambda s, qt: f"FORMAT_DATETIME('%B', CAST({s} as DATETIME))",
                "quarter_of_year": lambda s, qt: f"EXTRACT(QUARTER FROM {s})",
                "fiscal_quarter_of_year": lambda s, qt: (
                    f"EXTRACT(QUARTER FROM {self._fiscal_offset_to_timestamp(s, qt)})"
                ),
                "hour_of_day": lambda s, qt: f"CAST(CAST({s} AS STRING FORMAT 'HH24') AS INT64)",
                "day_of_week": lambda s, qt: f"CAST({s} AS STRING FORMAT 'DAY')",
                "day_of_month": lambda s, qt: f"EXTRACT(DAY FROM {s})",
                "day_of_year": lambda s, qt: f"EXTRACT(DAYOFYEAR FROM {s})",
            },
        }
        meta_lookup[Definitions.teradata] = {
            "raw": lambda s, qt: s,
            "time": lambda s, qt: f"CAST({s} AS TIMESTAMP)",
            "second": lambda s, qt: f"CAST(CAST({s} AS TIMESTAMP(0)) AS TIMESTAMP)",
            "minute": lambda s, qt: f"TRUNC(CAST({s} AS TIMESTAMP), 'MI')",
            "hour": lambda s, qt: f"TRUNC(CAST({s} AS TIMESTAMP), 'HH')",
            "date": lambda s, qt: f"CAST(TRUNC(CAST({s} AS TIMESTAMP), 'DD') AS TIMESTAMP)",
            "week": self._week_dimension_group_time_sql,
            "month": lambda s, qt: f"TRUNC(CAST({s} AS TIMESTAMP), 'MM')",
            "quarter": lambda s, qt: (
                f"CAST(EXTRACT(YEAR FROM CAST({s} AS TIMESTAMP)) AS VARCHAR(4))"
                f" || '-Q' || CAST(((EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP)) - 1) / 3 + 1)"
                f" AS VARCHAR(1))"
            ),
            "year": lambda s, qt: f"TRUNC(CAST({s} AS TIMESTAMP), 'YEAR')",
            "fiscal_month": lambda s, qt: (
                f"TRUNC(CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP), 'MM')"
            ),
            "fiscal_quarter": lambda s, qt: (
                f"CAST(EXTRACT(YEAR FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                f" AS VARCHAR(4)) || '-Q' || CAST(((EXTRACT(MONTH FROM"
                f" CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP)) - 1) / 3 + 1)"
                f" AS VARCHAR(1))"
            ),
            "fiscal_year": lambda s, qt: (
                f"TRUNC(CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP), 'YEAR')"
            ),
            "week_index": lambda s, qt: (
                f"((CAST({self._apply_week_start_day_offset_only(s, qt)} AS DATE)"
                f" - CAST(TRUNC(CAST({self._apply_week_start_day_offset_only(s, qt)} AS DATE), 'YEAR')"
                f" AS DATE)) / 7) + 1"
            ),
            "week_of_month": lambda s, qt: (
                f"((CAST({s} AS DATE) - CAST(TRUNC(CAST({s} AS DATE), 'MM') AS DATE)) / 7) + 1"
            ),
            "month_of_year_index": lambda s, qt: f"EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP))",
            "fiscal_month_of_year_index": lambda s, qt: (
                f"EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
            ),
            "month_of_year": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Mon')",
            "month_of_year_full_name": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Month')",
            "quarter_of_year": lambda s, qt: (
                f"((EXTRACT(MONTH FROM CAST({s} AS TIMESTAMP)) - 1) / 3 + 1)"
            ),
            "fiscal_quarter_of_year": lambda s, qt: (
                f"((EXTRACT(MONTH FROM CAST({self._fiscal_offset_to_timestamp(s, qt)} AS TIMESTAMP))"
                f" - 1) / 3 + 1)"
            ),
            "hour_of_day": lambda s, qt: f"EXTRACT(HOUR FROM CAST({s} AS TIMESTAMP))",
            "day_of_week": lambda s, qt: f"TO_CHAR(CAST({s} AS TIMESTAMP), 'Dy')",
            "day_of_month": lambda s, qt: f"EXTRACT(DAY FROM CAST({s} AS TIMESTAMP))",
            "day_of_year": lambda s, qt: (
                f"(CAST({s} AS DATE) - CAST(TRUNC(CAST({s} AS DATE), 'YEAR') AS DATE)) + 1"
            ),
        }
        # Snowflake and redshift have identical syntax in this case
        meta_lookup[Definitions.redshift] = meta_lookup[Definitions.snowflake]
        # Snowflake and duck db have identical syntax in this case
        meta_lookup[Definitions.duck_db] = meta_lookup[Definitions.postgres]
        # Azure Synapse and SQL Server have identical syntax
        meta_lookup[Definitions.azure_synapse] = meta_lookup[Definitions.sql_server]
        # Athena and Trino have identical syntax
        meta_lookup[Definitions.athena] = meta_lookup[Definitions.trino]
        # We alias month_name as the same thing as month_of_year to aid with looker migration
        for _, lookup in meta_lookup.items():
            lookup["month_name"] = lookup["month_of_year"]
            lookup["month_index"] = lookup["month_of_year_index"]
            lookup["fiscal_month_index"] = lookup["fiscal_month_of_year_index"]
            lookup["week_of_year"] = lookup["week_index"]

        if self.view.project.timezone and self.convert_timezone and self.dimension_group != "raw":
            sql = self._apply_timezone_to_sql(sql, self.view.project.timezone, query_type)
        return meta_lookup[query_type][self.dimension_group](sql, query_type)

    def _apply_timezone_to_sql(self, sql: str, timezone: str, query_type: str):
        # We need the second cast here in the case you apply the timezone with
        # the dimension group 'raw' to ensure they're the same initial type post-timezone transformation
        if query_type in {Definitions.snowflake, Definitions.databricks}:
            return f"CAST(CAST(CONVERT_TIMEZONE('{timezone}', {sql}) AS TIMESTAMP_NTZ) AS {self.datatype.upper()})"  # noqa
        elif query_type == Definitions.bigquery:
            return f"CAST(DATETIME(CAST({sql} AS TIMESTAMP), '{timezone}') AS {self.datatype.upper()})"
        elif query_type == Definitions.redshift:
            return f"CAST(CAST(CONVERT_TIMEZONE('{timezone}', CAST({sql} AS TIMESTAMP)) AS TIMESTAMP) AS {self.datatype.upper()})"  # noqa
        elif query_type in {Definitions.postgres, Definitions.duck_db, Definitions.trino, Definitions.athena}:
            return f"CAST(CAST({sql} AS TIMESTAMP) at time zone 'UTC' at time zone '{timezone}' AS {self.datatype.upper()})"  # noqa
        elif query_type == Definitions.mysql:
            return f"CONVERT_TZ({sql}, 'UTC', '{timezone}')"
        elif query_type in {Definitions.druid, Definitions.sql_server, Definitions.azure_synapse, Definitions.teradata}:
            print(
                f"Warning: {query_type.title()} does not support timezone conversion. "
                "Timezone will be ignored."
            )
            return sql
        else:
            raise QueryError(f"Unable to apply timezone to sql for query type {query_type}")

    def _fiscal_offset_to_timestamp(self, sql: str, query_type: str):
        offset_in_months = self.view.model.fiscal_month_offset
        if offset_in_months == 0:
            return sql
        elif query_type in {
            Definitions.snowflake,
            Definitions.redshift,
            Definitions.databricks,
            Definitions.sql_server,
            Definitions.azure_synapse,
        }:
            return f"DATEADD(MONTH, {offset_in_months}, {sql})"
        elif query_type == Definitions.teradata:
            return f"ADD_MONTHS({sql}, {offset_in_months})"
        elif query_type in {Definitions.postgres, Definitions.duck_db, Definitions.druid, Definitions.trino, Definitions.athena}:
            return f"{sql} + INTERVAL '{offset_in_months}' MONTH"
        elif query_type in {Definitions.bigquery, Definitions.mysql}:
            return f"DATE_ADD(CAST({sql} AS DATE), INTERVAL {offset_in_months} MONTH)"
        else:
            raise QueryError(
                f"Unable to find a valid method for running fiscal offset with query type {query_type}"
            )

    def _week_dimension_group_time_sql(self, sql: str, query_type: str):
        # Monday is the default date for warehouses
        week_start_day = self.view.week_start_day
        if week_start_day == "monday":
            return self._week_sql_date_trunc(sql, None, query_type)
        offset_lookup = {
            "sunday": 1,
            "saturday": 2,
            "friday": 3,
            "thursday": 4,
            "wednesday": 5,
            "tuesday": 6,
        }
        offset = offset_lookup[week_start_day]
        positioned_sql = self._week_sql_date_trunc(sql, offset, query_type)
        if query_type == Definitions.bigquery:
            positioned_sql = f"CAST({positioned_sql} AS {self.datatype.upper()})"
        return positioned_sql

    @staticmethod
    def _week_sql_date_trunc(sql, offset, query_type):
        casted = f"CAST({sql} AS DATE)"
        if query_type in {Definitions.snowflake, Definitions.redshift}:
            if offset is None:
                return f"DATE_TRUNC('WEEK', {casted})"
            return f"DATE_TRUNC('WEEK', {casted} + {offset}) - {offset}"
        elif query_type in {
            Definitions.postgres,
            Definitions.druid,
            Definitions.duck_db,
            Definitions.databricks,
            Definitions.trino,
            Definitions.athena,
        }:
            if offset is None:
                return f"DATE_TRUNC('WEEK', CAST({sql} AS TIMESTAMP))"
            return f"DATE_TRUNC('WEEK', CAST({sql} AS TIMESTAMP) + INTERVAL '{offset}' DAY) - INTERVAL '{offset}' DAY"  # noqa
        elif query_type == Definitions.bigquery:
            if offset is None:
                return f"DATE_TRUNC({casted}, ISOWEEK)"
            return f"DATE_TRUNC({casted} + {offset}, ISOWEEK) - {offset}"
        elif query_type in {Definitions.sql_server, Definitions.azure_synapse}:
            if offset is None:
                return f"DATEADD(WEEK, DATEDIFF(WEEK, 0, {casted}), 0)"
            return f"DATEADD(DAY, -{offset}, DATEADD(WEEK, DATEDIFF(WEEK, 0, DATEADD(DAY, {offset}, {casted})), 0))"  # noqa
        elif query_type == Definitions.mysql:
            if offset is None:
                return f"DATE_SUB({casted}, INTERVAL WEEKDAY({casted}) DAY)"
            # This takes the offset displayed as "days subtracted from monday"
            # into the day of week numbering that MySQL uses, so we can use operation below
            translated_offset = {
                0: 2,
                1: 1,
                2: 7,
                3: 6,
                4: 5,
                5: 4,
                6: 3,
            }
            return (
                f"DATE_SUB({casted}, INTERVAL ((DAYOFWEEK({casted}) - {translated_offset[offset]} + 7) % 7)"
                " DAY)"
            )
        elif query_type == Definitions.teradata:
            if offset is None:
                return f"TRUNC(CAST({sql} AS TIMESTAMP), 'IW')"
            return f"TRUNC(CAST({sql} AS TIMESTAMP) + INTERVAL '{offset}' DAY, 'IW') - INTERVAL '{offset}' DAY"  # noqa

        else:
            raise QueryError(f"Unable to find a valid method for running week with query type {query_type}")

    def _apply_week_start_day_offset_only(self, sql: str, query_type: str):
        # Monday is the default date for warehouses EXCEPT for BigQuery
        # So in BigQuery, we use ISOWEEK instead of WEEK, since ISOWEEK is monday based
        week_start_day = self.view.week_start_day
        offset_lookup = {
            "sunday": 1,
            "saturday": 2,
            "friday": 3,
            "thursday": 4,
            "wednesday": 5,
            "tuesday": 6,
        }
        # monday will result in None here which means no offsets will be applied
        offset = offset_lookup.get(week_start_day, None)
        casted = f"CAST({sql} AS DATE)"
        if query_type in {Definitions.snowflake, Definitions.redshift}:
            if offset is None:
                return f"DATE_TRUNC('DAY', {casted})"
            return f"DATE_TRUNC('DAY', {casted} + {offset})"
        elif query_type in {
            Definitions.postgres,
            Definitions.druid,
            Definitions.duck_db,
            Definitions.databricks,
            Definitions.trino,
            Definitions.athena,
        }:
            if offset is None:
                return f"DATE_TRUNC('DAY', CAST({sql} AS TIMESTAMP))"
            return f"DATE_TRUNC('DAY', CAST({sql} AS TIMESTAMP) + INTERVAL '{offset}' DAY)"
        elif query_type == Definitions.bigquery:
            if offset is None:
                return f"DATE_TRUNC({casted}, DAY)"
            return f"DATE_TRUNC({casted} + {offset}, DAY)"
        elif query_type in {Definitions.sql_server, Definitions.azure_synapse}:
            if offset is None:
                return f"CAST({casted} AS DATETIME)"
            return f"CAST(DATEADD(DAY, {offset}, {casted}) AS DATETIME)"  # noqa
        elif query_type == Definitions.mysql:
            if offset is None:
                return f"CAST({casted} AS DATETIME)"
            return f"CAST(DATE_ADD({casted}, INTERVAL {offset} DAY) AS DATETIME)"  # noqa
        elif query_type == Definitions.teradata:
            if offset is None:
                return f"TRUNC(CAST({sql} AS TIMESTAMP), 'DD')"
            return f"TRUNC(CAST({sql} AS TIMESTAMP) + INTERVAL '{offset}' DAY, 'DD')"
        else:
            raise QueryError(f"Unable to find a valid method for running offset with query type {query_type}")

    def _error(self, element, error, extra: dict = {}):
        line, column = self.line_col(element)
        return {
            **extra,
            "view_name": self.view.name,
            "field_name": self.name,
            "message": error,
            "line": line,
            "column": column,
            "reference_type": "field",
            "reference_id": self.id(capitalize_alias=True),
        }

    def collect_errors(self, metrics_must_have_dates: bool = True):
        warning_prefix = "Warning:"
        errors = []
        if not self.valid_name(self.name):
            errors.append(self._error(self.name, self.name_error("field", self.name)))
        elif (
            self.name in self.view.model.special_mapping_values
            and self.field_type != ZenlyticFieldType.dimension_group
        ):
            errors.append(
                self._error(
                    self.name,
                    (
                        f"Field name: {self.name} in view {self.view.name} is a reserved word and cannot be"
                        " used as a field name."
                    ),
                )
            )

        if self.field_type not in ZenlyticFieldType.options:
            errors.append(
                self._error(
                    self.field_type,
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid field_type"
                        f" {self.field_type}. Valid field_types are: {ZenlyticFieldType.options}"
                    ),
                )
            )

        if "type" not in self._definition:
            errors.append(
                self._error(
                    self.name,
                    f"Field {self.name} in view {self.view.name} is missing the required key 'type'.",
                )
            )

        if "label" in self._definition and not isinstance(self.label, str):
            errors.append(
                self._error(
                    self._definition["label"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid label {self.label}."
                        " label must be a string."
                    ),
                )
            )

        if "group_label" in self._definition and not isinstance(self.group_label, str):
            errors.append(
                self._error(
                    self._definition["group_label"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid group_label"
                        f" {self.group_label}. group_label must be a string."
                    ),
                )
            )

        if "hidden" in self._definition and not isinstance(self.hidden, bool):
            errors.append(
                self._error(
                    self._definition["hidden"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid hidden value of"
                        f" {self.hidden}. hidden must be a boolean (true or false)."
                    ),
                )
            )

        if "window" in self._definition and not isinstance(self.window, bool):
            errors.append(
                self._error(
                    self._definition["window"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid window value of"
                        f" {self.window}. window must be a boolean (true or false)."
                    ),
                )
            )

        if "percentile" in self._definition and not isinstance(self.percentile, int):
            errors.append(
                self._error(
                    self._definition["percentile"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid percentile value of"
                        f" {self.percentile}. percentile must be an integer between 1 and 99."
                    ),
                )
            )
        elif "percentile" in self._definition and self.percentile not in range(1, 100):
            errors.append(
                self._error(
                    self._definition["percentile"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid percentile value of"
                        f" {self.percentile}. percentile must be an integer between 1 and 99."
                    ),
                )
            )

        if "description" in self._definition and not isinstance(self.description, str):
            errors.append(
                self._error(
                    self._definition["description"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid description"
                        f" {self.description}. description must be a string."
                    ),
                )
            )

        # This value is pulled from the DESCRIPTION_MAX_CHARS constant in Zenlytic
        description_max_chars = 1024
        if "description" in self._definition and isinstance(self.description, str):
            if len(self.description) > description_max_chars:
                errors.append(
                    self._error(
                        self._definition["description"],
                        (
                            f"Warning: Field {self.name} in view {self.view.name} has a description that is"
                            f" too long ({len(self.description)} characters). Descriptions must be"
                            f" {description_max_chars} characters or less. It will be truncated to the first"
                            f" {description_max_chars} characters."
                        ),
                    )
                )

        if "zoe_description" in self._definition and not isinstance(self.zoe_description, str):
            errors.append(
                self._error(
                    self._definition["zoe_description"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid zoe_description"
                        f" {self.zoe_description}. zoe_description must be a string."
                    ),
                )
            )
        if "zoe_description" in self._definition and isinstance(self.zoe_description, str):
            if len(self.zoe_description) > description_max_chars:
                errors.append(
                    self._error(
                        self._definition["zoe_description"],
                        (
                            f"Warning: Field {self.name} in view {self.view.name} has a zoe_description that"
                            f" is too long. Descriptions must be {description_max_chars} characters or less."
                            f" It will be truncated to the first {description_max_chars} characters."
                        ),
                    )
                )

        if (
            "value_format_name" in self._definition
            and str(self.value_format_name) not in VALID_VALUE_FORMAT_NAMES
        ):
            errors.append(
                self._error(
                    self._definition["value_format_name"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid value_format_name"
                        f" {self.value_format_name}. Valid value_format_names are: {VALID_VALUE_FORMAT_NAMES}"
                    ),
                )
            )

        if "synonyms" in self._definition and not isinstance(self.synonyms, list):
            errors.append(
                self._error(
                    self._definition["synonyms"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid synonyms {self.synonyms}."
                        " synonyms must be a list of strings."
                    ),
                )
            )
        elif "synonyms" in self._definition:
            for synonym in self.synonyms:
                if not isinstance(synonym, str):
                    errors.append(
                        self._error(
                            self._definition["synonyms"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid synonym"
                                f" {synonym}. The synonym must be a string."
                            ),
                        )
                    )

        if "filters" in self._definition and not isinstance(self.filters, list):
            errors.append(
                self._error(
                    self._definition["filters"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid filters {self.filters}."
                        " The filters must be a list of filters, not an individual filter. In yaml syntax"
                        " use the '-' character to denote a list element."
                    ),
                )
            )
        elif "filters" in self._definition and isinstance(self.filters, list):
            for f in self.filters:
                if not isinstance(f, dict):
                    errors.append(
                        self._error(
                            self._definition["filters"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid filter {f}."
                                " filter must be a dictionary."
                            ),
                        )
                    )

                else:
                    if "field" in f and isinstance(f["field"], str) and "." not in f["field"]:
                        f["field"] = f"{self.view.name}.{f['field']}"

                    if "field" in f and f["field"] == f"{self.view.name}.{self.name}":
                        errors.append(
                            self._error(
                                f["field"],
                                (
                                    f"Field {self.name} in view {self.view.name} has a filter that references"
                                    " itself. This is invalid, and the filter will not be applied."
                                ),
                            )
                        )

                    errors.extend(
                        self.collect_field_filter_errors(
                            f,
                            self.view.project,
                            f"Field {self.name} filter",
                            "view",
                            self.view.name,
                            error_func=self._error,
                        )
                    )
                    errors.extend(
                        self.invalid_property_error(
                            f,
                            ["field", "value"],
                            "field filter",
                            f"in field {self.name} in view {self.view.name}",
                            error_func=self._error,
                        )
                    )

        if "extra" in self._definition and not isinstance(self.extra, dict):
            errors.append(
                self._error(
                    self._definition["extra"],
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid extra {self.extra}."
                        " The extra must be a dictionary."
                    ),
                )
            )

        errors.extend(
            self.view.collect_required_access_grant_errors(
                self._definition,
                self.view.project,
                f"in field {self.name} in view {self.view.name}",
                f"in model {self.view.model.name}",
                error_func=self._error,
            )
        )

        if "." in str(self.view.default_date):
            view_default_date = self.view.default_date
        else:
            view_default_date = f"{self.view.name}.{self.view.default_date}"

        if self.canon_date is not None and not isinstance(self.canon_date, str):
            errors.append(
                self._error(
                    self._definition.get("canon_date"),
                    (
                        f"Field {self.name} in view {self.view.name} has an invalid canon_date"
                        f" {self.canon_date}. canon_date must be a string."
                    ),
                )
            )
        elif self.canon_date is not None and self.canon_date != view_default_date:
            try:
                canon_date_field = self.view.project.get_field_by_name(self.canon_date)
                if (
                    canon_date_field.field_type != ZenlyticFieldType.dimension_group
                    or canon_date_field.type != "time"
                ):
                    errors.append(
                        self._error(
                            self._definition.get("canon_date"),
                            (
                                f"Canon date {self.canon_date} is not of field_type: dimension_group and"
                                f" type: time in field {self.name} in view {self.view.name}"
                            ),
                        )
                    )
            except (AccessDeniedOrDoesNotExistException, QueryError):
                errors.append(
                    self._error(
                        self._definition.get("canon_date"),
                        f"Canon date {self.canon_date} is unreachable in field {self.name}.",
                    )
                )

        # Dimension specific checks
        if self.field_type == ZenlyticFieldType.dimension:
            if str(self.type) not in ZenlyticType.dimension_options:
                errors.append(
                    self._error(
                        self._definition.get("type"),
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid type {self.type}."
                            f" Valid types for dimensions are: {ZenlyticType.dimension_options}"
                        ),
                    )
                )
            if (
                str(self.field_type) == ZenlyticFieldType.dimension
                and str(self.type) == ZenlyticType.string
                and not self.hidden
                and "searchable" not in self._definition
            ):
                errors.append(
                    self._error(
                        self._definition.get("searchable"),
                        (
                            f"Field {self.name} in view {self.view.name} does not have required 'searchable'"
                            " property set to either true or false. This property is required for"
                            " dimensions of type string that are not hidden."
                        ),
                        extra={"is_auto_fixable": True},
                    )
                )
            if "primary_key" in self._definition and not isinstance(self.primary_key, bool):
                errors.append(
                    self._error(
                        self._definition.get("primary_key"),
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid primary_key"
                            f" {self.primary_key}. primary_key must be a boolean (true or false)."
                        ),
                    )
                )

            if not isinstance(self._definition.get("sql"), str) and "case" not in self._definition:
                errors.append(
                    self._error(
                        self._definition.get("sql"),
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid sql"
                            f" {self._definition.get('sql')}. sql must be a string. The sql property must be"
                            " present for dimensions."
                        ),
                    )
                )
            elif "case" in self._definition:
                errors.append(
                    self._error(
                        self._definition.get("case"),
                        (
                            f"{warning_prefix} Field {self.name} in view {self.view.name} is using a case"
                            " statement, which is deprecated. Please use the sql property instead."
                        ),
                    )
                )
            elif self.sql is not None:
                errors.extend(self.collect_sql_errors(self.sql, "sql", error_func=self._error))

            if "tags" in self._definition and not isinstance(self.tags, list):
                errors.append(
                    self._error(
                        self._definition["tags"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid tags"
                            f" {self.tags}. tags must be a list of strings."
                        ),
                    )
                )
            elif "tags" in self._definition:
                for tag in self.tags:
                    if not isinstance(tag, str):
                        errors.append(
                            self._error(
                                self._definition["tags"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid tag {tag}."
                                    " tags must be a list of strings."
                                ),
                            )
                        )

            if "drill_fields" in self._definition and not isinstance(self._definition["drill_fields"], list):
                errors.append(
                    self._error(
                        self._definition["drill_fields"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid drill_fields"
                            ". drill_fields must be a list of strings."
                        ),
                    )
                )
            elif self.drill_fields is not None:
                for field_name in self.drill_fields:
                    try:
                        self.view.project.get_field(field_name)
                    except AccessDeniedOrDoesNotExistException:
                        errors.append(
                            self._error(
                                self._definition["drill_fields"],
                                (
                                    f"Field {field_name} in drill_fields is unreachable in field"
                                    f" {self.name} in view {self.view.name}."
                                ),
                            )
                        )

            if "searchable" in self._definition and not isinstance(self.searchable, bool):
                errors.append(
                    self._error(
                        self._definition["searchable"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid searchable"
                            f" {self.searchable}. searchable must be a boolean (true or false)."
                        ),
                    )
                )
            if "allow_higher_searchable_max" in self._definition and not isinstance(
                self.allow_higher_searchable_max, bool
            ):
                errors.append(
                    self._error(
                        self._definition["allow_higher_searchable_max"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid"
                            f" allow_higher_searchable_max {self.allow_higher_searchable_max}."
                            " allow_higher_searchable_max must be a boolean (true or false)."
                        ),
                    )
                )
            if self.type == ZenlyticType.tier:
                if "tiers" not in self._definition:
                    errors.append(
                        self._error(
                            self._definition["name"],
                            (
                                f"Field {self.name} in view {self.view.name} is of type tier, but does not"
                                " have a tiers property. The tiers property is required for dimensions of"
                                " type: tier."
                            ),
                        )
                    )
                elif "tiers" in self._definition and not isinstance(self.tiers, list):
                    errors.append(
                        self._error(
                            self._definition["tiers"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid tiers"
                                f" {self.tiers}. tiers must be a list of dictionaries."
                            ),
                        )
                    )
                elif "tiers" in self._definition:
                    for tier in self.tiers:
                        if not isinstance(tier, int):
                            errors.append(
                                self._error(
                                    tier,
                                    (
                                        f"Field {self.name} in view {self.view.name} has an invalid tier"
                                        f" {tier}. tiers must be a list of integers."
                                    ),
                                )
                            )
            if "link" in self._definition and not isinstance(self.link, str):
                errors.append(
                    self._error(
                        self._definition["link"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid link"
                            f" {self.link}. link must be a string."
                        ),
                    )
                )

        # Dimension group specific checks
        elif self.field_type == ZenlyticFieldType.dimension_group:
            if str(self.type) not in ZenlyticType.dimension_group_options:
                errors.append(
                    self._error(
                        self._definition.get("type"),
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid type {self.type}."
                            f" Valid types for dimension groups are: {ZenlyticType.dimension_group_options}"
                        ),
                    )
                )
            if "primary_key" in self._definition and not isinstance(self.primary_key, bool):
                errors.append(
                    self._error(
                        self._definition["primary_key"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid primary_key"
                            f" {self.primary_key}. primary_key must be a boolean (true or false)."
                        ),
                    )
                )
            # Handle time-specific properties
            if self.type == "time":
                if "intervals" in self._definition:
                    errors.append(
                        self._error(
                            self._definition["intervals"],
                            (
                                f"Field {self.name} in view {self.view.name} is of type time, but has"
                                " property intervals when it should have property timeframes"
                            ),
                        )
                    )

                if "timeframes" in self._definition and not isinstance(self.timeframes, list):
                    errors.append(
                        self._error(
                            self._definition["timeframes"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid timeframes"
                                f" {self.timeframes}. timeframes must be a list of strings."
                            ),
                        )
                    )
                else:
                    timeframes = self._definition.get("timeframes", [])
                    if not timeframes:
                        errors.append(
                            self._error(
                                self._definition["timeframes"],
                                (
                                    f"Field {self.name} in view {self.view.name} is of type time and but does"
                                    " not have values for the timeframe property. Add valid timeframes"
                                    f" (options: {VALID_TIMEFRAMES})"
                                ),
                            )
                        )
                    for i in timeframes:
                        if i not in VALID_TIMEFRAMES:
                            errors.append(
                                self._error(
                                    self._definition["timeframes"],
                                    (
                                        f"Field {self.name} in view {self.view.name} is of type time and has"
                                        f" timeframe value of '{i}' which is not a valid timeframes (valid"
                                        f" timeframes are {VALID_TIMEFRAMES})"
                                    ),
                                )
                            )
                if not isinstance(self._definition.get("sql"), str):
                    errors.append(
                        self._error(
                            self._definition["sql"],
                            (
                                f"Field {self.name} in view {self.view.name} is a dimension group of type"
                                " time, but does not have a sql valid property. Dimension groups of type"
                                " time must have a sql property and that property must be a string."
                            ),
                        )
                    )

                elif self.sql is not None:
                    errors.extend(self.collect_sql_errors(self.sql, "sql", error_func=self._error))

                if "convert_tz" in self._definition and not isinstance(self.convert_tz, bool):
                    errors.append(
                        self._error(
                            self._definition["convert_tz"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid convert_tz"
                                f" {self.convert_tz}. convert_tz must be a boolean (true or false)."
                            ),
                        )
                    )
                if "convert_timezone" in self._definition and not isinstance(self.convert_timezone, bool):
                    errors.append(
                        self._error(
                            self._definition["convert_timezone"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid convert_timezone"
                                f" {self.convert_timezone}. convert_timezone must be a boolean (true or"
                                " false)."
                            ),
                        )
                    )
                if "datatype" in self._definition and str(self.datatype) not in ZenlyticDataType.options:
                    errors.append(
                        self._error(
                            self._definition["datatype"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid datatype"
                                f" {self.datatype}. Valid datatypes for time dimension groups are:"
                                f" {ZenlyticDataType.options}"
                            ),
                        )
                    )

            # Handle duration-specific properties
            if self.type == "duration":
                if "timeframes" in self._definition:
                    errors.append(
                        self._error(
                            self._definition["timeframes"],
                            (
                                f"Field {self.name} in view {self.view.name} is of type duration, but has"
                                " property timeframes when it should have property intervals"
                            ),
                        )
                    )
                if self.type == "duration":
                    if "intervals" in self._definition and not isinstance(self.intervals, list):
                        errors.append(
                            self._error(
                                self._definition["intervals"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid intervals"
                                    f" {self.intervals}. intervals must be a list of strings."
                                ),
                            )
                        )
                    else:
                        intervals = self._definition.get("intervals", [])
                        if not intervals:
                            errors.append(
                                self._error(
                                    self._definition["intervals"],
                                    (
                                        f"Field {self.name} in view {self.view.name} is of type duration and"
                                        " but does not have values for the intervals property. Add valid"
                                        f" intervals (options: {VALID_INTERVALS})"
                                    ),
                                )
                            )
                        for i in intervals:
                            if i not in VALID_INTERVALS:
                                errors.append(
                                    self._error(
                                        self._definition["intervals"],
                                        (
                                            f"Field {self.name} in view {self.view.name} is of type duration"
                                            f" and has interval value of '{i}' which is not a valid interval"
                                            f" (valid intervals are {VALID_INTERVALS})"
                                        ),
                                    )
                                )
                    if "sql" in self._definition:
                        errors.append(
                            self._error(
                                self._definition["sql"],
                                (
                                    f"Field {self.name} in view {self.view.name} is a dimension group of type"
                                    " duration, but has a sql property. Dimension groups of type duration"
                                    " must not have a sql property (just sql_start and sql_end)."
                                ),
                            )
                        )

                    for property_name, sql_param in zip(
                        ["sql_start", "sql_end"], [self.sql_start, self.sql_end]
                    ):
                        if not isinstance(self._definition.get(property_name), str):
                            errors.append(
                                self._error(
                                    self._definition.get(property_name),
                                    (
                                        f"Field {self.name} in view {self.view.name} has an invalid"
                                        f" {property_name} {self._definition.get(property_name)}."
                                        f" {property_name} must be a string. The {property_name} property"
                                        " must be present for dimension groups of type duration."
                                    ),
                                )
                            )
                        elif sql_param is not None:
                            errors.extend(self.collect_sql_errors(sql_param, "sql", error_func=self._error))

        # Measure specific checks
        elif self.field_type == ZenlyticFieldType.measure:
            if str(self.type) not in ZenlyticType.measure_options:
                errors.append(
                    self._error(
                        self._definition.get("type"),
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid type {self.type}."
                            f" Valid types for measures are: {ZenlyticType.measure_options}"
                        ),
                    )
                )
            if "primary_key" in self._definition:
                errors.append(
                    self._error(
                        self._definition["primary_key"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid primary_key"
                            f" {self.primary_key}. primary_key is not a valid property for measures."
                        ),
                    )
                )
            if not self.canon_date:
                if self.is_merged_result:
                    error_text = (
                        f"Field {self.name} in view {self.view.name} is a merged result metric (measure),"
                        " but does not have a date associated with it. Associate a date with the metric"
                        " (measure) by setting either the canon_date property on the measure itself or"
                        " the default_date property on the view the measure is in. Merged results are"
                        " not possible without associated dates."
                    )
                    errors.append(self._error(self._definition["name"], error_text))
                elif metrics_must_have_dates:
                    error_text = (
                        f"{warning_prefix} Field {self.name} in view {self.view.name} is a metric (measure),"
                        " but does not have a date associated with it. Associate a date with the metric"
                        " (measure) by setting either the canon_date property on the measure itself or the"
                        " default_date property on the view the measure is in. Time periods and merged"
                        " results will not be possible to use until you define the date association"
                    )
                    errors.append(self._error(self._definition["name"], error_text))
            if "sql" not in self._definition and self.type != ZenlyticType.cumulative:
                errors.append(
                    self._error(
                        self._definition["name"],
                        (
                            f"Field {self.name} in view {self.view.name} is a measure, but does not have a"
                            " sql property. Measures must have a sql property unless they are cumulative."
                        ),
                    )
                )

            elif self.type != ZenlyticType.cumulative and not isinstance(self._definition["sql"], str):
                errors.append(
                    self._error(
                        self._definition["sql"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid sql"
                            f" {self._definition['sql']}. sql must be a string."
                        ),
                    )
                )
            elif self.sql is not None and self.type != ZenlyticType.cumulative:
                errors.extend(self.collect_sql_errors(self.sql, "sql", error_func=self._error))

            if "is_merged_result" in self._definition and not isinstance(self.is_merged_result, bool):
                errors.append(
                    self._error(
                        self._definition["is_merged_result"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid is_merged_result"
                            f" {self.is_merged_result}. is_merged_result must be a boolean (true or false)."
                        ),
                    )
                )

            if self.type == ZenlyticType.cumulative:
                if "measure" not in self._definition:
                    errors.append(
                        self._error(
                            self._definition["name"],
                            (
                                f"Field {self.name} in view {self.view.name} is a cumulative metric"
                                " (measure), but does not have a measure property."
                            ),
                        )
                    )
                elif not isinstance(self._definition["measure"], str):
                    errors.append(
                        self._error(
                            self._definition["measure"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid measure"
                                f" {self._definition['measure']}. measure must be a string."
                            ),
                        )
                    )
                try:
                    measure = self.measure
                    if measure is None:
                        raise QueryError(
                            f"Measure {self._definition.get('measure')} is unreachable in field"
                            f" {self.name} in view {self.view.name}."
                        )
                    if measure.field_type != ZenlyticFieldType.measure:
                        errors.append(
                            self._error(
                                self._definition["measure"],
                                (
                                    f"Field {self.name} in view {self.view.name} is a cumulative metric"
                                    " (measure), but the measure property"
                                    f" {self._definition.get('measure')} is not a measure."
                                ),
                            )
                        )
                except (AccessDeniedOrDoesNotExistException, QueryError):
                    errors.append(
                        self._error(
                            self._definition["name"],
                            (
                                f"Field {self.name} in view {self.view.name} is a cumulative metric"
                                f" (measure), but the measure property {self._definition.get('measure')} is"
                                " unreachable."
                            ),
                        )
                    )
                if "cumulative_where" in self._definition and not isinstance(self.cumulative_where, str):
                    errors.append(
                        self._error(
                            self._definition["cumulative_where"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid cumulative_where"
                                f" {self.cumulative_where}. cumulative_where must be a string."
                            ),
                        )
                    )
                if "update_where_timeframe" in self._definition and not isinstance(
                    self.update_where_timeframe, bool
                ):
                    errors.append(
                        self._error(
                            self._definition["update_where_timeframe"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid"
                                f" update_where_timeframe {self.update_where_timeframe}."
                                " update_where_timeframe must be a boolean (true or false)."
                            ),
                        )
                    )
            if self.type in ZenlyticType.requires_sql_distinct_key and not self.sql_distinct_key:
                errors.append(
                    self._error(
                        self._definition["name"],
                        (
                            f"Field {self.name} in view {self.view.name} is a measure of type {self.type},"
                            " but does not have a sql_distinct_key property."
                        ),
                    )
                )
            elif self.sql_distinct_key and not isinstance(self.sql_distinct_key, str):
                errors.append(
                    self._error(
                        self._definition["sql_distinct_key"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid sql_distinct_key"
                            f" {self.sql_distinct_key}. sql_distinct_key must be a string."
                        ),
                    )
                )
            elif self.sql_distinct_key:
                for field_to_replace in self.fields_to_replace(self.sql_distinct_key):
                    if field_to_replace == "TABLE":
                        continue
                    try:
                        self.get_field_with_view_info(field_to_replace)
                    except AccessDeniedOrDoesNotExistException:
                        errors.append(
                            self._error(
                                self._definition["sql_distinct_key"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid"
                                    f" sql_distinct_key {self.sql_distinct_key}. The field"
                                    f" {field_to_replace} referenced in sql_distinct_key does not exist."
                                ),
                            )
                        )

            if "non_additive_dimension" in self._definition and not isinstance(
                self._definition["non_additive_dimension"], dict
            ):
                errors.append(
                    self._error(
                        self._definition["non_additive_dimension"],
                        (
                            f"Field {self.name} in view {self.view.name} has an invalid"
                            f" non_additive_dimension {self._definition['non_additive_dimension']}."
                            " non_additive_dimension must be a dictionary."
                        ),
                    )
                )
            elif "non_additive_dimension" in self._definition:
                if "name" not in self._definition["non_additive_dimension"]:
                    errors.append(
                        self._error(
                            self._definition["non_additive_dimension"],
                            (
                                f"Field {self.name} in view {self.view.name} has an invalid"
                                f" non_additive_dimension {self.non_additive_dimension}."
                                " non_additive_dimension must have a 'name' property that references a type"
                                " time dimension group."
                            ),
                        )
                    )
                elif self.non_additive_dimension:
                    try:
                        referenced_field = self.get_field_with_view_info(self.non_additive_dimension["name"])
                        if (
                            referenced_field.field_type != ZenlyticFieldType.dimension_group
                            or referenced_field.type != "time"
                        ):
                            errors.append(
                                self._error(
                                    self._definition["non_additive_dimension"]["name"],
                                    (
                                        f"Field {self.name} in view {self.view.name} has an invalid"
                                        " non_additive_dimension. The field"
                                        f" {self._definition['non_additive_dimension']['name']} referenced in"
                                        " non_additive_dimension is not a valid dimension group with type"
                                        " time."
                                    ),
                                )
                            )
                    except AccessDeniedOrDoesNotExistException:
                        errors.append(
                            self._error(
                                self._definition["non_additive_dimension"]["name"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid"
                                    " non_additive_dimension. The field"
                                    f" {self._definition['non_additive_dimension']['name']} referenced in"
                                    " non_additive_dimension does not exist."
                                ),
                            )
                        )
                    if str(self.non_additive_dimension.get("window_choice")) not in ["max", "min"]:
                        errors.append(
                            self._error(
                                self._definition["non_additive_dimension"]["window_choice"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid"
                                    " non_additive_dimension. window_choice must be"
                                    " either 'max' or 'min'."
                                ),
                            )
                        )
                    if not isinstance(
                        self.non_additive_dimension.get("window_aware_of_query_dimensions", True), bool
                    ):
                        errors.append(
                            self._error(
                                self._definition["non_additive_dimension"][
                                    "window_aware_of_query_dimensions"
                                ],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid"
                                    " non_additive_dimension."
                                    " window_aware_of_query_dimensions must be a boolean."
                                ),
                            )
                        )
                    if not isinstance(self.non_additive_dimension.get("nulls_are_equal", False), bool):
                        errors.append(
                            self._error(
                                self._definition["non_additive_dimension"]["nulls_are_equal"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid"
                                    " non_additive_dimension."
                                    " nulls_are_equal must be a boolean."
                                ),
                            )
                        )
                    if not isinstance(self.non_additive_dimension.get("window_groupings", []), list):
                        errors.append(
                            self._error(
                                self._definition["non_additive_dimension"]["window_groupings"],
                                (
                                    f"Field {self.name} in view {self.view.name} has an invalid"
                                    " non_additive_dimension. window_groupings must be"
                                    " a list."
                                ),
                            )
                        )
                    else:
                        for grouping in self.non_additive_dimension.get("window_groupings", []):
                            try:
                                referenced_field = self.get_field_with_view_info(grouping)
                                if referenced_field.field_type not in {
                                    ZenlyticFieldType.dimension_group,
                                    ZenlyticFieldType.dimension,
                                }:
                                    errors.append(
                                        self._error(
                                            self._definition["non_additive_dimension"]["window_groupings"],
                                            (
                                                f"Field {self.name} in view {self.view.name} has an invalid"
                                                f" non_additive_dimension. The field {grouping} referenced in"
                                                " window_groupings is not a valid dimension or dimension"
                                                " group."
                                            ),
                                        )
                                    )
                            except AccessDeniedOrDoesNotExistException:
                                errors.append(
                                    self._error(
                                        self._definition["non_additive_dimension"]["window_groupings"],
                                        (
                                            f"Field {self.name} in view {self.view.name} has an invalid"
                                            " non_additive_dimension. The field"
                                            f" {grouping} referenced in window_groupings does not exist."
                                        ),
                                    )
                                )
                    errors.extend(
                        self.invalid_property_error(
                            self.non_additive_dimension,
                            [
                                "name",
                                "window_choice",
                                "window_aware_of_query_dimensions",
                                "nulls_are_equal",
                                "window_groupings",
                            ],
                            "non additive dimension",
                            f"in field {self.name} in view {self.view.name}",
                            error_func=self._error,
                        )
                    )

        # Catch invalid attributes for all field types
        # (this property is scoped based on field_type)
        properties = self.valid_properties + self.internal_properties
        errors.extend(
            self.invalid_property_error(
                self._definition,
                properties,
                "field",
                f"{self.name} in view {self.view.name}",
                error_func=self._error,
            )
        )
        # For dynamic fields everything is a warning
        if self.is_dynamic_field:
            errors = [
                {**e, "message": f"{warning_prefix} {e['message']}"}
                for e in errors
                if warning_prefix not in e
            ]
        return errors

    def collect_sql_errors(self, sql: str, property_name: str, error_func):
        errors = []

        refs = self.get_referenced_sql_query(strings_only=False)
        if refs is None:
            error_text = (
                f"Field {self.name} in view {self.view.name} contains invalid SQL in property"
                f" {property_name}. Remove any Looker parameter references from the SQL."
            )
            errors.append(error_func(sql, error_text))
        else:
            for ref in refs:
                if isinstance(ref, str):
                    error_text = (
                        f"Field {self.name} in view {self.view.name} contains invalid field reference {ref}."
                    )
                    errors.append(error_func(sql, error_text))
                elif isinstance(ref, Field) and ref.id() == self.id():
                    error_text = (
                        f"Field {self.name} in view {self.view.name} contains a reference to itself. This is"
                        " invalid. Please remove the reference. If you're trying to reference a column in a"
                        " table, you can use ${TABLE}."
                    )
                    error_text += self.name
                    errors.append(error_func(sql, error_text))
                elif (
                    self.field_type != ZenlyticFieldType.measure
                    and isinstance(ref, Field)
                    and ref.field_type == ZenlyticFieldType.measure
                ):
                    error_text = (
                        f"Field {self.name} in view {self.view.name} contains invalid field reference"
                        f" {ref.name}. Dimensions and Dimension Groups cannot reference measures."
                    )
                    errors.append(error_func(sql, error_text))
        return errors

    @staticmethod
    def static_sql_validation(sql: str, query_type: str):
        pass

    def get_referenced_sql_query(self, strings_only=True):
        if self.sql and ("{%" in self.sql or self.sql == ""):
            return None

        if self.type == "cumulative":
            referenced_fields = [self.measure]
        elif self.type == "duration" and self.sql_start and self.sql_end:
            start_fields = self.referenced_fields(self.sql_start)
            end_fields = self.referenced_fields(self.sql_end)
            referenced_fields = start_fields + end_fields
        else:
            referenced_fields = self.referenced_fields(self.sql)

        if strings_only:
            valid_references = [f for f in referenced_fields if not isinstance(f, str)]
            return list(set(f.id() for f in valid_references))
        return referenced_fields

    @functools.lru_cache(maxsize=None)
    def referenced_fields(self, sql):
        reference_fields = []
        if sql is None:
            return []

        for to_replace in self.fields_to_replace(sql):
            if to_replace != "TABLE":
                try:
                    field = self.get_field_with_view_info(to_replace)

                except AccessDeniedOrDoesNotExistException:
                    field = None
                to_replace_type = None if field is None else field.type

                if to_replace_type == ZenlyticType.number and field.field_type == ZenlyticFieldType.measure:
                    reference_fields_raw = field.get_referenced_sql_query(strings_only=False)
                    if reference_fields_raw is not None:
                        reference_fields.extend(reference_fields_raw)
                elif to_replace_type is None and field is None:
                    reference_fields.append(to_replace)
                else:
                    reference_fields.append(field)

        return reference_fields

    def referenced_window_functions(self, sql) -> List[Any]:
        pass

    def get_replaced_sql_query(
        self, query_type: str, alias_only: bool = False, render_window_functions: bool = False
    ):
        if self.sql:
            clean_sql = self._replace_sql_query(
                self.sql, query_type, alias_only=alias_only, render_window_functions=render_window_functions
            )
            if self.field_type == ZenlyticFieldType.dimension_group and self.type == "time":
                clean_sql = self.apply_dimension_group_time_sql(clean_sql, query_type)
            return clean_sql

        if self.sql_start and self.sql_end and self.type == "duration":
            clean_sql_start = self._replace_sql_query(
                self.sql_start,
                query_type,
                alias_only=alias_only,
                render_window_functions=render_window_functions,
            )
            clean_sql_end = self._replace_sql_query(
                self.sql_end,
                query_type,
                alias_only=alias_only,
                render_window_functions=render_window_functions,
            )
            return self.apply_dimension_group_duration_sql(clean_sql_start, clean_sql_end, query_type)

        if self.type == "cumulative":
            raise QueryError(
                f"You cannot call sql_query() on cumulative type field {self.id()} because cumulative "
                "queries are dependent on the 'FROM' clause to be correct and the sql_query() method "
                "only returns the aggregation of the individual metric, not the whole SQL query. "
                "To see the query, use get_sql_query() with the cumulative metric."
            )

        raise QueryError(f"Unknown type of SQL query for field {self.name}")

    def _replace_sql_query(
        self, sql_query: str, query_type: str, alias_only: bool = False, render_window_functions: bool = False
    ):
        if sql_query is None or "{%" in sql_query or sql_query == "":
            return None
        clean_sql = self.replace_fields(
            sql_query, query_type, alias_only=alias_only, render_window_functions=render_window_functions
        )
        clean_sql = re.sub(r"[ ]{2,}", " ", clean_sql)
        clean_sql = clean_sql.replace("'", "'")
        return clean_sql

    def replace_fields(
        self, sql, query_type, view_name=None, alias_only=False, render_window_functions: bool = False
    ):
        clean_sql = copy(sql)
        view_name = self.view.name if not view_name else view_name
        fields_to_replace = self.fields_to_replace(sql)
        for to_replace in fields_to_replace:
            if to_replace == "TABLE":
                if alias_only:
                    clean_sql = clean_sql.replace("${TABLE}.", "")
                else:
                    clean_sql = clean_sql.replace("${TABLE}", view_name)
            else:
                field = self.get_field_with_view_info(to_replace, specified_view=view_name)
                if field and field.window and not render_window_functions:
                    sql_replace = field.alias(with_view=True)
                elif field:
                    sql_replace = field.raw_sql_query(
                        query_type, alias_only=alias_only, render_window_functions=render_window_functions
                    )
                else:
                    sql_replace = to_replace
                if isinstance(sql_replace, list):
                    raise QueryError(
                        f"Field {self.name} has the wrong type. You must use the type 'number' "
                        f"if you reference other measures in your expression (like {to_replace} "
                        "referenced here)"
                    )
                clean_sql = clean_sql.replace("${" + to_replace + "}", sql_replace)
        return clean_sql.strip()

    def get_field_with_view_info(self, field: str, specified_view: str = None):
        view_name, field_name = self.field_name_parts(field)
        if view_name is None and specified_view is None:
            view_name = self.view.name
        elif view_name is None and specified_view:
            view_name = specified_view

        if self.view is None:
            raise AttributeError(f"You must specify which view this field is in '{self.name}'")
        return self.view.project.get_field(field_name, view_name=view_name)

    def _translate_looker_tier_to_sql(self, sql: str, tiers: list):
        pass

    @staticmethod
    def _translate_looker_case_to_sql(case: dict):
        pass

    def _clean_sql_for_case(self, sql: str):
        pass

    def _derive_query_type(self) -> str:
        model = self.view.model
        if model is None:
            raise QueryError(
                f"Could not find a model in field {self.alias()} to use to detect the query type, "
                "please pass the query type explicitly using the query_type argument"
                "or pass an model name using the model_name argument"
            )
        connection_type = self.view.project.connection_lookup.get(model.connection)
        if connection_type is None:
            raise QueryError(
                f"Could not find the connection named {model.connection} "
                f"in model {model.name} to use in detecting the query type, "
                "please pass the query type explicitly using the query_type argument"
            )
        return connection_type

    def _add_view_name_if_needed(self, field_name: str):
        pass

    def non_additive_alias(self):
        pass

    def non_additive_cte_alias(self):
        pass

    def is_cumulative(self):
        explicitly_cumulative = self.type == "cumulative"
        if self.sql:
            has_references = False
            for field in self.referenced_fields(self.sql):
                if not isinstance(field, str) and field.type == "cumulative":
                    has_references = True
                    break
        else:
            has_references = False
        return explicitly_cumulative or has_references

    @staticmethod
    def collect_field_filter_errors(
        field_filter: dict, project, prefix: str, entity_name: str, name: str, error_func
    ):
        errors = []
        location = f"{entity_name.title()} {name}"
        if "field" not in field_filter:
            errors.append(
                error_func(field_filter, f"{prefix} in {location} is missing the required field property")
            )
        elif "field" in field_filter:
            try:
                project.get_field(field_filter["field"])
            except AccessDeniedOrDoesNotExistException:
                errors.append(
                    error_func(
                        field_filter["field"],
                        (
                            f"{prefix} in {location} is referencing a field, {field_filter['field']} that"
                            " does not exist"
                        ),
                    )
                )
        if "value" not in field_filter:
            errors.append(
                error_func(field_filter, f"{prefix} in {location} is missing the required value property")
            )
        elif "value" in field_filter and not isinstance(field_filter["value"], str):
            try:
                Filter(field_filter).filter_dict()
            except Exception:
                errors.append(
                    error_func(
                        field_filter["value"],
                        (
                            f"{prefix} in {location} has an invalid value property. Valid values can be found"
                            " here in the docs: https://docs.zenlytic.com/docs/data_modeling/field_filter"
                        ),
                    )
                )

        return errors

    @staticmethod
    def _name_is_not_valid_sql(name: str):
        pass

    @functools.lru_cache(maxsize=None)
    def join_graphs(self):
        if self.view.model is None:
            raise QueryError(
                f"Could not find a model in view {self.view.name}, "
                "please pass the model or set the model_name argument in the view"
            )
        # We need to pick the most restricted join graph based on all other
        # views referenced in the SQL of this field.
        sql_references = self.get_referenced_sql_query(strings_only=False)
        referenced_views = set([self.view.name])

        # First, we get the views that are referenced, and put them in a set.
        if sql_references is not None:
            for ref in sql_references:
                if isinstance(ref, Field):
                    referenced_views.add(ref.view.name)

        # Then, we get the weakly connected references to EACH view that is referenced in the SQL
        base_collection = []
        for view_name in referenced_views:
            base_collection.append(set(self.view.project.join_graph.weak_join_graph_hashes(view_name)))

        # Finally, we get intersection of the set of the weakly connected references
        # to EACH view that is referenced in the SQL, to get the most restricted
        # join graph that can actually be joined to this field
        base = list(set.intersection(*base_collection))

        if self.is_cumulative():
            return base

        edges = self.view.project.join_graph.merged_results_graph(self.view.model).in_edges(self.id())
        extended = self._wrap_with_model_name([f"merged_result_{mr}" for mr, _ in edges])

        if self.loses_join_ability_with_other_views():
            return extended
        return list(sorted(base + extended))

    def _wrap_with_model_name(self, join_graphs: list):
        if len(models := self.view.project.models()) > 1:
            model_index = [m.name for m in models].index(self.view.model.name)
            return [f"m{model_index}_{jg}" for jg in join_graphs]
        return join_graphs
