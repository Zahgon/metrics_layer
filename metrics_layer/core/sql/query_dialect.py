from enum import Enum
from typing import Any, Optional

from pypika import Field, Query, Table
from pypika.dialects import (
    MSSQLQueryBuilder,
    MySQLQueryBuilder,
    PostgreSQLQueryBuilder,
    QueryBuilder,
)
from pypika.enums import Dialects
from pypika.utils import builder, format_quotes

from metrics_layer.core.model.definitions import Definitions

PostgreSQLQueryBuilder.ALIAS_QUOTE_CHAR = None
PostgreSQLQueryBuilder.QUOTE_CHAR = None
MySQLQueryBuilder.ALIAS_QUOTE_CHAR = None
MySQLQueryBuilder.QUOTE_CHAR = None


class NullSorting(Enum):
    first = "FIRST"
    last = "LAST"


class QueryBuilderWithOrderByNullsOption(QueryBuilder):
    @builder
    def replace_table(self, current_table: Optional[Table], new_table: Optional[Table]) -> "QueryBuilder":
        """
        Replaces all occurrences of the specified table with the new table. Useful when reusing fields across
        queries.

        :param current_table:
            The table instance to be replaces.
        :param new_table:
            The table instance to replace with.
        :return:
            A copy of the query with the tables replaced.
        """
        pass

    @builder
    def orderby(self, *fields: Any, **kwargs: Any) -> "QueryBuilder":
        pass

    def _orderby_sql(
        self,
        quote_char: Optional[str] = None,
        alias_quote_char: Optional[str] = None,
        orderby_alias: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Produces the ORDER BY part of the query.  This is a list of fields and possibly their
        directionality, ASC or DESC and null sorting option (FIRST or LAST).
        The clauses are stored in the query under self._orderbys as a list of tuples
        containing the field, directionality (which can be None),
        and null sorting option (which can be None).

        If an order by field is used in the select clause,
        determined by a matching, and the orderby_alias
        is set True then the ORDER BY clause will use
        the alias, otherwise the field will be rendered as SQL.
        """
        pass


class SnowflakeQuery(Query):
    """
    Defines a query class for use with Snowflake.
    """

    @classmethod
    def _builder(cls, **kwargs) -> "SnowflakeQueryBuilderWithOrderByNullsOption":
        pass


class SnowflakeQueryBuilderWithOrderByNullsOption(QueryBuilderWithOrderByNullsOption):
    QUOTE_CHAR = None
    ALIAS_QUOTE_CHAR = None
    QUERY_ALIAS_QUOTE_CHAR = ""
    QUERY_CLS = SnowflakeQuery

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(dialect=Dialects.SNOWFLAKE, **kwargs)


class MySQLQuery(Query):
    """
    Defines a query class for use with MySQL.
    """

    @classmethod
    def _builder(cls, **kwargs) -> "MySQLQueryBuilder":
        pass


class PostgresQuery(Query):
    """
    Defines a query class for use with Snowflake.
    """

    @classmethod
    def _builder(cls, **kwargs) -> PostgreSQLQueryBuilder:
        pass


class PostgresQueryWithOrderByNullsOption(Query):
    """
    Defines a query class for use with Snowflake.
    """

    @classmethod
    def _builder(cls, **kwargs) -> "PostgreSQLQueryBuilderWithOrderByNullsOption":
        pass


class PostgreSQLQueryBuilderWithOrderByNullsOption(
    PostgreSQLQueryBuilder, QueryBuilderWithOrderByNullsOption
):
    QUERY_CLS = PostgresQueryWithOrderByNullsOption


class RedshiftQuery(Query):
    """
    Defines a query class for use with Amazon Redshift.
    """

    @classmethod
    def _builder(cls, **kwargs) -> "RedShiftQueryBuilderWithOrderByNullsOption":
        pass


class RedShiftQueryBuilderWithOrderByNullsOption(QueryBuilderWithOrderByNullsOption):
    ALIAS_QUOTE_CHAR = None
    QUOTE_CHAR = None
    QUERY_CLS = RedshiftQuery


class MSSQLQueryBuilderCorrectLimit(MSSQLQueryBuilder):
    QUOTE_CHAR = None

    @builder
    def limit(self, limit: int):
        pass


class MSSSQLQuery(Query):
    """
    Defines a query class for use with Microsoft SQL Server (and other T-SQL flavors).
    """

    @classmethod
    def _builder(cls, **kwargs) -> MSSQLQueryBuilderCorrectLimit:
        pass


class TeradataQueryBuilderWithTop(PostgreSQLQueryBuilderWithOrderByNullsOption):
    QUERY_CLS = None  # Set below after TeradataQuery is defined

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._top = None

    @builder
    def limit(self, limit: int):
        pass

    def _select_sql(self, **kwargs):
        pass


class TeradataQuery(Query):
    """
    Defines a query class for use with Teradata. Uses TOP N instead of LIMIT N.
    """

    @classmethod
    def _builder(cls, **kwargs) -> TeradataQueryBuilderWithTop:
        pass


TeradataQueryBuilderWithTop.QUERY_CLS = TeradataQuery


query_lookup = {
    Definitions.snowflake: SnowflakeQuery,
    Definitions.bigquery: SnowflakeQuery,  # In terms of quoting, these are the same
    Definitions.redshift: RedshiftQuery,
    Definitions.postgres: PostgresQueryWithOrderByNullsOption,
    Definitions.druid: PostgresQuery,  # druid core query logic is postgres compatible, minus null sorting
    Definitions.duck_db: PostgresQueryWithOrderByNullsOption,  # duck db core query logic = postgres
    Definitions.databricks: PostgresQueryWithOrderByNullsOption,  # databricks core query logic = postgres
    Definitions.trino: PostgresQueryWithOrderByNullsOption,  # trino core query logic = postgres
    Definitions.sql_server: MSSSQLQuery,
    Definitions.azure_synapse: MSSSQLQuery,  # Azure Synapse is a T-SQL flavor
    Definitions.mysql: MySQLQuery,
    Definitions.teradata: TeradataQuery,
    Definitions.athena: PostgresQueryWithOrderByNullsOption,  # athena core query logic = postgres (trino)
}

if_null_lookup = {
    Definitions.snowflake: "ifnull",
    Definitions.bigquery: "ifnull",
    Definitions.redshift: "nvl",
    Definitions.postgres: "coalesce",
    Definitions.databricks: "coalesce",
    Definitions.druid: "nvl",
    Definitions.duck_db: "coalesce",
    Definitions.trino: "coalesce",
    Definitions.sql_server: "isnull",
    Definitions.azure_synapse: "isnull",
    Definitions.mysql: "ifnull",
    Definitions.teradata: "coalesce",
    Definitions.athena: "coalesce",
}
