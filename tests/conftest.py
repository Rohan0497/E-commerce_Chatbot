import types
import pytest


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


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """
    Automatically set the required model env var for all tests.
    """
    monkeypatch.setenv("GROQ_MODEL", "dummy-model")
    yield
