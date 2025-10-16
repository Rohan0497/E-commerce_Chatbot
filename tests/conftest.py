import types
from typing import Any, Dict, List

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyChoice:
    def __init__(self, content: str):
        self.message = types.SimpleNamespace(content=content)


class DummyCompletion:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]


class DummyGroq:
    """
    Minimal mock for groq.Groq that supports:
    client.chat.completions.create(...)
    """
    def __init__(self, content: str):
        self._content = content
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        return DummyCompletion(self._content)


class DummySQLTool:
    """Deterministic SQL tool behavior for agent-focused tests."""

    def __init__(self):
        self.last_query = ""
        self.rows: List[Dict[str, Any]] = []
        self.columns: List[str] = []
        self.raise_non_select = False

    def sql_generate(self, args: Dict[str, Any]) -> Dict[str, str]:
        return {"sql_wrapped": "<SQL>SELECT * FROM product;</SQL>"}

    def sql_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        sql = args["sql"]
        self.last_query = sql
        if self.raise_non_select:
            raise ValueError("Only SELECT statements are allowed.")
        return {"rows": self.rows, "columns": self.columns}

    def verbalize(self, args: Dict[str, Any]) -> Dict[str, str]:
        return {"text": "verbalized"}


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """
    Automatically set the required model env var for all tests.
    """
    monkeypatch.setenv("GROQ_MODEL", "dummy-model")
    yield
