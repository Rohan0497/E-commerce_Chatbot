"""
Central configuration for the E-commerce Bot application.
Loads environment variables from a .env file at import time.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# --- Load .env early so everything importing config sees the vars ---
# This looks for a .env in the current working dir or parents.
load_dotenv()

#: Environment variable names
GROQ_API_KEY_ENV = "GROQ_API_KEY"
GROQ_MODEL_ENV = "GROQ_MODEL"

#: Default embedding model for the router.
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

#: Path to the SQLite database file (can be overridden in tests).
DB_PATH = Path(__file__).resolve().parent / "db.sqlite"

#: Path to the FAQ CSV.
FAQ_CSV_PATH = Path(__file__).resolve().parent / "resources" / "faq_data.csv"


def require_env(var_name: str) -> str:
    """
    Return the value of an environment variable or raise a clear error.

    Raises
    ------
    RuntimeError
        If the environment variable is missing or empty.
    """
    try:
        value = os.environ[var_name]
    except KeyError as exc:
        raise RuntimeError(f"Required environment variable '{var_name}' is not set.") from exc
    if not value:
        raise RuntimeError(f"Environment variable '{var_name}' is empty.")
    return value


def get_groq_api_key() -> str:
    """
    Convenience accessor specifically for the Groq API key.
    """
    return require_env(GROQ_API_KEY_ENV)
