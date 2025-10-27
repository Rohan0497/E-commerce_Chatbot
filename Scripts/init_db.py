"""Initialize and seed the product SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import get_db_path

DEFAULT_CSV = Path("app") / "resources" / "ecommerce_data_final.csv"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product (
    product_link TEXT,
    title TEXT,
    brand TEXT,
    price INTEGER,
    discount FLOAT,
    avg_rating FLOAT,
    total_ratings INTEGER
);
"""


def load_seed_rows(csv_path: Path) -> pd.DataFrame:
    required_cols = [
        "product_link",
        "title",
        "brand",
        "price",
        "discount",
        "avg_rating",
        "total_ratings",
    ]
    if not csv_path.exists():
        raise FileNotFoundError(f"Seed CSV not found at {csv_path}")

    df = pd.read_csv(csv_path)
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Seed CSV missing columns: {', '.join(sorted(missing))}")
    return df[required_cols]


def init_db(db_path: Path, seed_path: Path) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = load_seed_rows(seed_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute("DELETE FROM product")
        df.to_sql("product", conn, if_exists="append", index=False)
        conn.commit()
    return len(df)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the product database.")
    default_db = get_db_path()
    parser.add_argument("--db-path", type=Path, default=default_db, help=f"SQLite path (default: {default_db})")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help=f"Seed CSV (default: {DEFAULT_CSV})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = init_db(args.db_path, args.csv)
    print(f"Initialized database at {args.db_path} with {rows} products from {args.csv}.")


if __name__ == "__main__":
    main()
