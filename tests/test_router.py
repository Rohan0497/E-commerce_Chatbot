from app.router import build_router, RouteName


def test_routing_intents():
    r = build_router()
    assert r("How are you?").name == RouteName.SMALL_TALK
    assert r("What is the return policy of the products?").name == RouteName.FAQ
    assert r("Are there any Puma shoes on sale?").name == RouteName.SQL
