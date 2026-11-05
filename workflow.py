"""Generate, validate, execute, and explain a BI query."""

import logging
from dataclasses import dataclass
from time import perf_counter

import pandas as pd
from sqlalchemy.exc import DBAPIError

from executor import execute_sql
from explainer import explain
from sql_generator import ModelError, correct_sql, generate_sql
from sql_validator import validate_sql

LOGGER = logging.getLogger(__name__)
MAX_RETRIES = 2


@dataclass
class PipelineResult:
    sql: str | None = None
    dataframe: pd.DataFrame | None = None
    explanation: str = ""
    error: str | None = None
    generation_seconds: float = 0.0
    execution_seconds: float = 0.0
    total_seconds: float = 0.0
    retries: int = 0


def run_pipeline(question, semantic_layer):
    result = PipelineResult()
    start = perf_counter()
    try:
        question = question.strip()
        if not question:
            result.error = "Saisissez une question."
            return result

        timer = perf_counter()
        try:
            generated = generate_sql(question, semantic_layer)
        finally:
            result.generation_seconds += perf_counter() - timer

        candidate = generated["sql"]
        if not candidate:
            result.error = generated["explanation"] or "La demande ne peut pas être traitée."
            return result

        for attempt in range(MAX_RETRIES + 1):
            valid, reason, cleaned = validate_sql(candidate)
            if not valid:
                result.error = f"Requête refusée. {reason}"
                return result
            result.sql = cleaned

            timer = perf_counter()
            try:
                result.dataframe = execute_sql(cleaned)
            except DBAPIError as error:
                db_error = str(error.orig)
            finally:
                result.execution_seconds += perf_counter() - timer

            if result.dataframe is not None:
                break
            if attempt == MAX_RETRIES:
                result.error = "PostgreSQL n’a pas pu exécuter la requête après deux corrections."
                return result

            result.retries += 1
            timer = perf_counter()
            try:
                candidate = correct_sql(question, semantic_layer, cleaned, db_error)
            finally:
                result.generation_seconds += perf_counter() - timer

        try:
            result.explanation = explain(question, result.sql, result.dataframe)
        except ModelError:
            LOGGER.warning("Explication Ollama indisponible.")
            result.explanation = (
                "La requête n’a renvoyé aucune ligne." if result.dataframe.empty
                else f"La requête a renvoyé {len(result.dataframe)} ligne(s). "
                     "Le détail figure dans le tableau. Le résumé automatique est indisponible."
            )
        return result
    except ModelError as error:
        result.error = str(error)
        return result
    finally:
        result.total_seconds = perf_counter() - start
        LOGGER.info(
            "generation_s=%.3f execution_s=%.3f total_s=%.3f retries=%d success=%s",
            result.generation_seconds, result.execution_seconds, result.total_seconds,
            result.retries, result.error is None and result.dataframe is not None,
        )
