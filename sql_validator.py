"""Validate generated SQL against the bundled PostgreSQL data access policy."""

import re
from functools import lru_cache

from sqlglot import ErrorLevel, exp, parse
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from config import load_semantic_layer

MAX_ROWS = 1000
DIALECT = "postgres"

# A closed set prevents unreviewed PostgreSQL functions, operators, and SQL clauses
# from becoming executable as new constructs are added to SQLGlot.
SAFE_NODES = frozenset("""
    Add Alias And Avg Between Boolean Case Cast Column Count CTE CurrentDate
    CurrentTimestamp DataType DataTypeParam DenseRank Distinct Div EQ Exists Extract
    Filter From Group GT GTE Having Identifier If ILike In Interval Is Join Lag Lead
    Like Limit Literal LT LTE Max Min Mod Mul Neg NEQ Not Null Nullif Offset Or Order
    Ordered Paren Rank Round RowNumber Select Star Sub Subquery Sum Table TableAlias
    TimestampTrunc DateTrunc TryCast Union Var Where Window WindowSpec With
    Coalesce Upper Lower Length Trim Abs
""".split())
SAFE_TYPES = frozenset("""
    BIGINT BOOLEAN DATE DECIMAL DOUBLE FLOAT INT SMALLINT TEXT TIME TIMESTAMP TIMESTAMPTZ VARCHAR
""".split())
TIME_UNITS = frozenset("""
    YEAR YEARS QUARTER QUARTERS MONTH MONTHS WEEK WEEKS DAY DAYS HOUR HOURS
    MINUTE MINUTES SECOND SECONDS DOW ISODOW DOY ISOYEAR EPOCH DECADE CENTURY
    MILLISECOND MILLISECONDS MICROSECOND MICROSECONDS
""".split())


@lru_cache(maxsize=1)
def _policy():
    layer = load_semantic_layer()
    return (
        set(layer["allowed_tables"]),
        {column.rsplit(".", 1)[-1] for column in layer["sensitive_columns"]},
        {"public": layer["schema"]},
    )


def _check_syntax(query, sensitive):
    limit = query.args.get("limit")
    count = limit.expression if isinstance(limit, exp.Limit) else None
    if (
        not isinstance(count, exp.Literal)
        or count.is_string
        or not re.fullmatch(r"[0-9]{1,4}", count.this)
        or not 1 <= int(count.this) <= MAX_ROWS
    ):
        raise ValueError("Un LIMIT entier compris entre 1 et 1000 est requis au niveau principal.")

    for node in query.walk():
        if type(node).__name__ not in SAFE_NODES:
            raise ValueError(f"Construction SQL non autorisée ({type(node).__name__}).")
        if isinstance(node, exp.Identifier):
            if node.name.casefold() in sensitive:
                raise ValueError("Accès à une colonne sensible refusé.")
            if not 1 <= len(node.name.encode("utf-8")) <= 63:
                raise ValueError("Longueur d’identifiant PostgreSQL invalide.")
        if isinstance(node, exp.Star):
            if not isinstance(node.parent, exp.Count) or node.parent.this is not node or any(node.args.values()):
                raise ValueError("Énumérez les colonnes à lire. COUNT(*) est autorisé.")
        if isinstance(node, exp.DataType) and node.this.name not in SAFE_TYPES:
            raise ValueError("Type de conversion SQL non autorisé.")
        if isinstance(node, exp.Var) and node.name.upper() not in TIME_UNITS:
            raise ValueError("Unité de temps SQL non autorisée.")
        if isinstance(node, exp.With) and node.recursive:
            raise ValueError("Les CTE récursives sont interdites.")
        if isinstance(node, exp.Join) and node.args.get("method"):
            raise ValueError("Utilisez une condition de jointure explicite.")
        if isinstance(node, exp.TableAlias) and node.columns:
            raise ValueError("Nommez les colonnes dans la projection SELECT.")


def _bind_sources(query, allowed_tables):
    base_tables = []
    seen_tables = set()
    relation_aliases = set()
    for scope in traverse_scope(query):
        for alias, (reference, source) in scope.selected_sources.items():
            relation_aliases.add(alias)
            if isinstance(reference, exp.Table):
                seen_tables.add(id(reference))
            if isinstance(source, exp.Table):
                if (
                    not isinstance(source.this, exp.Identifier)
                    or source.catalog
                    or source.db not in ("", "public")
                    or source.name not in allowed_tables
                ):
                    raise ValueError(f"Table non autorisée ({source.sql(dialect=DIALECT, comments=False)}).")
                base_tables.append(source)

    if any(id(table) not in seen_tables for table in query.find_all(exp.Table)):
        raise ValueError("Source de données non reconnue.")
    for column in query.find_all(exp.Column):
        if not column.table and column.name in relation_aliases:
            raise ValueError("La lecture d’une ligne entière est interdite.")

    for table in base_tables:
        table.set("db", exp.to_identifier("public"))


def validate_sql(sql):
    """Return (is_valid, error_msg, cleaned_sql); execute only cleaned_sql."""
    if not isinstance(sql, str) or not sql.strip() or "\x00" in sql or len(sql) > 20_000:
        return False, "Requête SQL vide ou invalide.", None

    try:
        statements = parse(sql, read=DIALECT, error_level=ErrorLevel.RAISE)
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union)):
            return False, "Une seule requête SELECT est autorisée.", None
        query = normalize_identifiers(statements[0], dialect=DIALECT)
        allowed_tables, sensitive, schema = _policy()
        _check_syntax(query, sensitive)
        _bind_sources(query, allowed_tables)
        # Analyze a copy so column checking preserves the original result labels.
        qualify(query.copy(), dialect=DIALECT, schema=schema, expand_stars=False)
        cleaned = query.sql(dialect=DIALECT, comments=False, unsupported_level=ErrorLevel.RAISE)
        return True, None, cleaned
    except (SqlglotError, ValueError, RecursionError) as error:
        return False, str(error), None
