"""SQL tooling helpers for the agent loop."""

from __future__ import annotations

import re
import sqlite3
import logging
from typing import Any, Dict, Iterable, List, Optional

from groq import Groq

from app.config import DB_PATH, GROQ_MODEL_ENV, require_env

logger = logging.getLogger(__name__)

SQL_SYSTEM_PROMPT = (
    "You are an expert in understanding the database schema and generating SQL queries for a natural "
    "language question asked pertaining to the data you have. The schema is provided in the schema tags.\n"
    "<schema>\n"
    "table: product\n\n"
    "fields:\n"
    "product_link - string (hyperlink to product)\n"
    "title - string (name of the product)\n"
    "brand - string (brand of the product)\n"
    "price - integer (price of the product in Indian Rupees)\n"
    "discount - float (discount on the product. 10 percent discount is represented as 0.1, 20 percent as 0.2, and such.)\n"
    "avg_rating - float (average rating of the product. Range 0-5, 5 is the highest.)\n"
    "total_ratings - integer (total number of ratings for the product)\n"
    "</schema>\n"
    "Make sure whenever you try to search for the brand name, the name can be in any case.\n"
    "So, make sure to use %LIKE% to find the brand in condition. Never use 'ILIKE'.\n"
    "Create a single SQL query for the question provided.\n"
    "The query should have all the fields in SELECT clause (i.e. SELECT *).\n"
    "Just the SQL query is needed, nothing more. Always provide the SQL in between the <SQL></SQL> tags."
)

COMPREHENSION_SYSTEM_PROMPT = (
    "You are an expert in understanding the context of the question and replying based on the data "
    "pertaining to the question provided. You will be provided with Question: and Data:. The data "
    "will be in the form of an array or a dataframe or dict. Reply based only on the data provided "
    "as Data for answering the question asked as Question. Do not write anything like 'Based on the data' "
    "or any other technical words. Just a plain simple natural language response.\n"
    "The Data would always be in context to the question asked. For example if the question is "
    "\"What is the average rating?\" and data is \"4.3\", then answer should be \"The average rating for the "
    "product is 4.3\". Make sure the response is curated with the question and data.\n"
    "There can also be cases where you are given an entire dataframe in the Data: field. Always remember "
    "that the data field contains the answer of the question asked. Always reply in the following format when "
    "listing products (one per line):\n"
    "<Title>: Rs.<price> (<discount%> off), Rating: <avg_rating> <link>"
)

ALLOWED_TABLES = {"product"}
ALLOWED_COLUMNS = {
    "product_link",
    "title",
    "brand",
    "price",
    "discount",
    "avg_rating",
    "total_ratings",
}
RESERVED_TOKENS = {
    "select",
    "distinct",
    "from",
    "where",
    "and",
    "or",
    "group",
    "by",
    "order",
    "asc",
    "desc",
    "limit",
    "as",
    "like",
    "lower",
    "upper",
    "count",
    "avg",
    "sum",
    "min",
    "max",
    "case",
    "when",
    "then",
    "end",
    "in",
    "on",
    "not",
    "between",
}


def _build_groq(client: Optional[Groq]) -> Groq:
    """Return a Groq client (or reuse injected mock)."""
    if client is not None:
        return client
    return Groq()


def sql_generate(
    question: str,
    *,
    model: Optional[str] = None,
    client: Optional[Groq] = None,
) -> Dict[str, str]:
    """Generate a SQL statement wrapped in <SQL> tags for the question."""
    groq_client = _build_groq(client)
    resolved_model = model or require_env(GROQ_MODEL_ENV)
    completion = groq_client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    sql_wrapped = completion.choices[0].message.content
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Generated SQL for question='%s': %s", question, sql_wrapped)
    return {"sql_wrapped": sql_wrapped}


def _ensure_limit(sql: str) -> str:
    """Append LIMIT 50 if no limit is present."""
    if re.search(r"\blimit\b", sql, flags=re.IGNORECASE):
        return sql
    stripped = sql.strip().rstrip(";")
    suffix = ";" if sql.strip().endswith(";") else ""
    return f"{stripped} LIMIT 50{suffix}"


def _validate_sql_structure(sql: str) -> None:
    """Enforce basic read-only and whitelist rules."""
    upper_sql = sql.upper()
    if not upper_sql.strip().startswith("SELECT"):
        raise ValueError("Only SELECT statements are allowed.")
    forbidden = ("UPDATE", "INSERT", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "ATTACH", "DETACH")
    if any(keyword in upper_sql for keyword in forbidden):
        raise ValueError("Only read-only SELECT statements are permitted.")

    # Ensure only allowed tables are referenced.
    tables = re.findall(r"\bFROM\s+([a-zA-Z_][\w]*)", upper_sql)
    tables += re.findall(r"\bJOIN\s+([a-zA-Z_][\w]*)", upper_sql)
    for table in tables:
        if table.lower() not in ALLOWED_TABLES:
            raise ValueError(f"Table '{table}' is not allowed.")

    # Check column usage in SELECT clause.
    match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Malformed SELECT statement.")
    column_expr = match.group(1).strip()
    if column_expr == "*":
        return

    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", column_expr)
    for token in tokens:
        token_lower = token.lower()
        if token_lower in RESERVED_TOKENS:
            continue
        if token_lower in ALLOWED_TABLES:
            continue
        if token_lower not in ALLOWED_COLUMNS:
            raise ValueError(f"Column '{token}' is not allowed.")


def _run_sql(sql: str, db_path: str) -> tuple[List[sqlite3.Row], List[str]]:
    """Execute SQL returning sqlite3.Row rows and column metadata."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        description = cursor.description or []
        columns = [col[0] for col in description]
        return rows, columns


def sql_run(
    sql: str,
    *,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Execute a validated SELECT query and return rows/columns.

    Returns
    -------
    Dict[str, Any]
        {"rows": [dict], "columns": [str]}
    """
    _validate_sql_structure(sql)
    limited_sql = _ensure_limit(sql)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Executing SQL (with guards applied): %s", limited_sql)
    rows, columns = _run_sql(limited_sql, db_path)
    records = [dict(row) for row in rows]
    return {"rows": records, "columns": columns}


def verbalize(
    question: str,
    data: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    client: Optional[Groq] = None,
) -> Dict[str, str]:
    """Generate a natural language description of the SQL result set."""
    groq_client = _build_groq(client)
    resolved_model = model or require_env(GROQ_MODEL_ENV)
    completion = groq_client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": COMPREHENSION_SYSTEM_PROMPT},
            {"role": "user", "content": f"QUESTION: {question}\nDATA: {data}"},
        ],
        temperature=0.2,
    )
    text = completion.choices[0].message.content
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Verbalized %d rows for question='%s'", len(data), question)
    return {"text": text}
