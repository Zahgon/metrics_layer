# This takes an incoming SQL statement and converts the MQL() section of it
# into our internal format, asks the main query method to resolve the sql
# for that configuration then replaces the MQL() section of the original string
# with the correct SQL

from copy import copy, deepcopy

import sqlparse
from sqlparse.sql import Function, Identifier, IdentifierList, Statement, Where
from sqlparse.tokens import Keyword, Whitespace

from metrics_layer.core.sql.query_errors import ParseError
from metrics_layer.core.sql.resolve import SQLQueryResolver


class MQLConverter:
    """
    Syntax here is:

    MQL(
        metric_name
        BY
        dimension
        WHERE
        condition
        HAVING
        having_condition
        ORDER BY
        metric_name
    )

    which will resolve to the SQL query that gives that result.

    The MQL feature can be used to compose SQL queries as well, as follows

    SELECT
        countries.country,
        metric_by_country.metric_name
    SELECT countries
        LEFT JOIN
            MQL(
                metric_name
                BY
                country
                WHERE
                condition
                HAVING
                having_condition
                ORDER BY
                metric_name
            ) as metric_by_country
            ON metric_by_country.country=countries.country

    The syntax can also be used for event / funnel queries, as follows:

    SELECT
        *
    FROM MQL(
            total_revenue, number_of_users

            FOR events
            FUNNEL event_name = 'user_created'
            THEN event_name = 'complete_onboarding' as onboarding,
                        event_name = 'purchase' as made_a_purchase
            WITHIN 3 days
            BY region, new_vs_repeat
            WHERE region != 'West' AND new_vs_repeat <> 'New'
        ) as subquery
    """

    def __init__(self, sql: str, project, **kwargs):
        self._function_name = "MQL"
        self.sql = sql
        self.project = project
        self.kwargs = kwargs
        self.connection = None

    def get_query(self):
        pass

    def parse_and_resolve_mql(self, token):
        pass

    def resolve_mql_statement(self, mql_statement):
        pass

    def _resolve_mode(self, token, mode):
        pass

    def _add_by_mode(self, metrics: list, dimensions: list, mode: str, identifier: str):
        pass

    @staticmethod
    def _tokens_to_sql(tokens: list):
        pass

    def _is_funnel(self, token):
        pass
