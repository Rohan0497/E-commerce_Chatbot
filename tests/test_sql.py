import sqlite3
from pathlib import Path

import pandas as pd

from app import sql as sqlmod
from tests.conftest import DummyGroq


def make_temp_db(tmp_path: Path) -> Path:
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE product(
                product_link TEXT,
                title TEXT,
                brand TEXT,
                price INTEGER,
                discount REAL,
                avg_rating REAL,
                total_ratings INTEGER
            );
        """
        )
        conn.execute(
            """
            INSERT INTO product VALUES
                ('http://x/1','Alpha Shoe','Nike',2999,0.5,4.9,1000),
                ('http://x/2','Runner II','Puma',4999,0.3,4.7,500);
        """
        )
    return db


def test_extract_sql_tagged():
    text = "<SQL>SELECT * FROM product;</SQL>"
    assert sqlmod._extract_sql_tagged(text) == "SELECT * FROM product;"
    assert sqlmod._extract_sql_tagged("no tags") is None


def test_run_query_select_only(tmp_path: Path):
    db = make_temp_db(tmp_path)
    df = sqlmod.run_query("SELECT * FROM product", db_path=db)
    assert len(df) == 2

    assert sqlmod.run_query("DELETE FROM product", db_path=db) is None


def test_sql_chain_happy_path(tmp_path: Path, monkeypatch):
    db = make_temp_db(tmp_path)
    # Mock generate_sql_query to return a tagged query
    monkeypatch.setattr(
        sqlmod,
        "generate_sql_query",
        lambda q, client=None, model=None: "<SQL>SELECT * FROM product;</SQL>",
    )
    # Mock LLM for data comprehension
    answer = sqlmod.sql_chain("All products", client=DummyGroq("OK"), model="dummy", db_path=db)
    assert answer == "OK"


def test_generate_sql_query_calls_groq():
    out = sqlmod.generate_sql_query("q", client=DummyGroq("<SQL>SELECT * FROM product;</SQL>"), model="dummy")
    assert "<SQL>" in out


def test_data_comprehension_uses_llm():
    out = sqlmod.data_comprehension("Q", [{"a": 1}], client=DummyGroq("ANS"), model="dummy")
    assert out == "ANS"
