"""Execute validated SQL in a bounded, read-only PostgreSQL transaction."""

from functools import lru_cache

import pandas as pd
from sqlalchemy import URL, create_engine

from config import DB_STATEMENT_TIMEOUT_MS, db_settings
from sql_validator import validate_sql


@lru_cache(maxsize=1)
def _engine():
    settings = db_settings()
    url = URL.create(
        "postgresql+psycopg2",
        username=settings["user"],
        password=settings["password"],
        host=settings["host"],
        port=settings["port"],
        database=settings["dbname"],
    )
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": settings["connect_timeout"]})


def execute_sql(sql):
    """Return a pandas DataFrame, or propagate the original database exception."""
    valid, error, cleaned_sql = validate_sql(sql)
    if not valid:
        raise ValueError(error)
    if DB_STATEMENT_TIMEOUT_MS <= 0:
        raise ValueError("DB_STATEMENT_TIMEOUT_MS doit être strictement positif.")

    with _engine().begin() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        connection.exec_driver_sql("SET LOCAL search_path = pg_catalog")
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'Africa/Casablanca'")
        connection.exec_driver_sql("SET LOCAL standard_conforming_strings = on")
        connection.exec_driver_sql(f"SET LOCAL statement_timeout = {DB_STATEMENT_TIMEOUT_MS}")
        frame = pd.read_sql_query(cleaned_sql, connection.execution_options(no_parameters=True))

    if not frame.columns.is_unique:
        frame.columns = [f"{column} ({index})" for index, column in enumerate(frame.columns, 1)]
    return frame
