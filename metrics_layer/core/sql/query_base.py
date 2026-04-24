import re
from copy import deepcopy
from typing import Union

import sqlparse
from pypika import JoinType
from pypika.terms import LiteralValue
from sqlparse.tokens import Name, Punctuation

from metrics_layer.core.model.base import MetricsLayerBase
from metrics_layer.core.model.join import Join, ZenlyticJoinType
from metrics_layer.core.sql.query_filter import MetricsLayerFilter


class MetricsLayerQueryBase(MetricsLayerBase):
    def _base_query(self):
        pass

    def get_where_with_aliases(
        self, filters: list, project, cte_alias_lookup: dict = {}, raise_if_not_in_lookup: bool = False
    ):
        pass

    @staticmethod
    def parse_identifiers_from_clause(clause: str):
        pass

    @staticmethod
    def get_pypika_join_type(join: Join):
        pass

    @staticmethod
    def pypika_join_type_lookup(join_type: str):
        pass

    @staticmethod
    def sql(sql: str, alias: Union[None, str] = None):
        pass

    @staticmethod
    def strip_alias(sql: str):
        pass


class QueryKindTypes:
    merged = "MERGED"
    single = "SINGLE"
