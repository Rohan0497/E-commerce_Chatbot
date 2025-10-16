"""
SQL generation and data answer synthesis using Groq and SQLite.

Pipeline
1) generate_sql_query(): ask LLM to produce SELECT query wrapped in <SQL> tags
2) _extract_sql_tagged(): extract SQL from tags
3) run_query(): execute only SELECTs against SQLite
4) data_comprehension(): ask LLM to verbalize tabular results
5) sql_chain(): orchestrate the above and return a final answer
"""
from __future__ import annotations

import re
import sqlite3
from typing import Optional, Sequence, Any, Dict

import pandas as pd
from dotenv import load_dotenv
from groq import Groq

from app.config import DB_PATH, GROQ_MODEL_ENV, require_env

load_dotenv()

SQL_SYSTEM_PROMPT = (
    "You are an expert in understanding the database schema and generating SQL queries for a natural "
    "language question asked pertaining to the data you have. The schema is provided in the schema tags.\n"
    "<schema>\n"
    "table: product\n\n"
    "fields:\n"
    "product_link - string (hyperlink to product)\t\n"
    "title - string (name of the product)\t\n"
    "brand - string (brand of the product)\t\n"
    "price - integer (price of the product in Indian Rupees)\t\n"
    "discount - float (discount on the product. 10 percent discount is represented as 0.1, 20 percent as 0.2, and such.)\t\n"
    "avg_rating - float (average rating of the product. Range 0-5, 5 is the highest.)\t\n"
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
    "“What is the average rating?” and data is “4.3”, then answer should be “The average rating for the "
    "product is 4.3”. Make sure the response is curated with the question and data.\n"
    "There can also be cases where you are given an entire dataframe in the Data: field. Always remember "
    "that the data field contains the answer of the question asked. Always reply in the following format when "
    "listing products (one per line):\n"
    "1. <Title>: Rs. <price> (<discount percent> percent off), Rating: <avg_rating> <link>"
)


def _client() -> Groq:
    """Return a Groq client (mockable for tests)."""
    return Groq()


def generate_sql_query(question: str, client: Optional[Groq] = None, model: Optional[str] = None) -> str:
    """
    Generate a SQL query in <SQL> tags for the given question.

    Notes
    -----
    The LLM is instructed to return *only* a single SQL statement and to
    wrap it in <SQL>...</SQL>.

    Returns
    -------
    str
        Raw LLM message content (expected to include <SQL>...</SQL>).
    """
    if client is None:
        client = _client()
    if model is None:
        model = require_env(GROQ_MODEL_ENV)

    chat_completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return chat_completion.choices[0].message.content  # type: ignore[no-any-return]


def _extract_sql_tagged(text: str) -> Optional[str]:
    """
    Extract the first SQL string between <SQL>...</SQL> tags.

    Returns
    -------
    Optional[str]
        SQL string or None if tags not present.
    """
    matches = re.findall(r"<SQL>(.*?)</SQL>", text, flags=re.DOTALL | re.IGNORECASE)
    if not matches:
        return None
    return matches[0].strip()


def run_query(sql: str, db_path=DB_PATH) -> Optional[pd.DataFrame]:
    """
    Execute a SELECT query against the configured SQLite database.

    Safety
    ------
    - Only executes statements that begin with SELECT (case-insensitive).
    - Everything else returns None.

    Returns
    -------
    Optional[pd.DataFrame]
        Query results if SELECT, else None.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return None
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn)
    return df


def data_comprehension(
    question: str,
    context: Sequence[Dict[str, Any]],
    client: Optional[Groq] = None,
    model: Optional[str] = None,
) -> str:
    """
    Turn structured data into a natural-language answer via LLM.

    Returns
    -------
    str
        Natural language answer that reflects the provided data.
    """
    if client is None:
        client = _client()
    if model is None:
        model = require_env(GROQ_MODEL_ENV)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": COMPREHENSION_SYSTEM_PROMPT},
            {"role": "user", "content": f"QUESTION: {question}\nDATA: {context}"},
        ],
        temperature=0.2,
    )
    return completion.choices[0].message.content  # type: ignore[no-any-return]


def sql_chain(
    question: str,
    client: Optional[Groq] = None,
    model: Optional[str] = None,
    db_path=DB_PATH,
) -> str:
    """
    High-level chain: generate SQL, execute it, and verbalize the result.

    Returns
    -------
    str
        Final natural-language answer or an error message.
    """
    sql_wrapped = generate_sql_query(question, client=client, model=model)
    extracted = _extract_sql_tagged(sql_wrapped)
    if not extracted:
        return "Sorry, the model could not generate a SQL query for your question."
    df = run_query(extracted, db_path=db_path)
    if df is None:
        return "Sorry, there was a problem executing the SQL query."
    context = df.to_dict(orient="records")
    return data_comprehension(question, context, client=client, model=model)
