from app.smalltalk import talk
from tests.conftest import DummyGroq


def test_smalltalk_uses_groq_mock():
    client = DummyGroq("Hello! I'm just a mock.")
    out = talk("How are you?", client=client, model="dummy")
    assert "mock" in out
