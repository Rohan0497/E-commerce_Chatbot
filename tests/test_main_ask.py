import types

from app.router import RouteName
from app import router as routermod
from main import ask


def test_ask_routes_to_handlers(monkeypatch):
    # Fake router returning names in sequence
    names = [RouteName.FAQ, RouteName.SQL, RouteName.SMALL_TALK, "unknown"]

    def fake_router(q):
        name = names.pop(0)
        return types.SimpleNamespace(name=name)

    monkeypatch.setattr(routermod, "router", fake_router)
    monkeypatch.setattr("app.faq.faq_chain", lambda q: "FAQ")
    monkeypatch.setattr("app.sql.sql_chain", lambda q: "SQL")
    monkeypatch.setattr("app.smalltalk.talk", lambda q: "SMALL")

    assert ask("q1") == "FAQ"
    assert ask("q2") == "SQL"
    assert ask("q3") == "SMALL"
    assert ask("q4").startswith("Route ")
