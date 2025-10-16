"""
Natural-language router using semantic intent matching.

This module defines:
- `RouteName`: canonical route names for handlers.
- `build_router()`: factory returning a configured `SemanticRouter`.
- `router`: a module-level router instance.

The router is deterministic given a fixed embedding model. It routes to:
1) FAQ
2) SQL
3) SMALL_TALK
"""

from __future__ import annotations

from dataclasses import dataclass
import types
from typing import List, Sequence

try:  # pragma: no cover - optional dependency
    from semantic_router import Route, SemanticRouter
    from semantic_router.encoders import HuggingFaceEncoder
except ImportError:  # pragma: no cover - fallback path exercised in tests
    Route = None  # type: ignore[assignment]
    SemanticRouter = None  # type: ignore[misc]
    HuggingFaceEncoder = None  # type: ignore[assignment]


@dataclass(frozen=True)
class RouteName:
    FAQ: str = "faq"
    SQL: str = "sql"
    SMALL_TALK: str = "small-talk"


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _keyword_router():
    faq_terms = {"policy", "refund", "return", "shipping", "payment", "warranty", "order"}
    sql_terms = {
        "shoe",
        "shoes",
        "price",
        "cost",
        "discount",
        "brand",
        "rating",
        "size",
        "list",
        "show",
        "buy",
        "product",
        "puma",
        "nike",
    }

    class KeywordRouter:
        def __call__(self, query: str):
            lowered = query.lower()
            if _contains(lowered, faq_terms):
                name = RouteName.FAQ
            elif _contains(lowered, sql_terms):
                name = RouteName.SQL
            else:
                name = RouteName.SMALL_TALK
            return types.SimpleNamespace(name=name)

    return KeywordRouter()


def _contains(text: str, needles: Sequence[str]) -> bool:
    return any(term in text for term in needles)


def build_router():
    """
    Create and return a configured `SemanticRouter` instance.

    Returns
    -------
    SemanticRouter
    """
    if SemanticRouter is None or HuggingFaceEncoder is None or Route is None:
        return _keyword_router()

    encoder = HuggingFaceEncoder(name=DEFAULT_EMBEDDING_MODEL)

    faq = Route(
        name=RouteName.FAQ,
        utterances=[
            "What is the return policy of the products?",
            "Do I get discount with the HDFC credit card?",
            "How can I track my order?",
            "What payment methods are accepted?",
            "How long does it take to process a refund?",
            "What is your policy on defective product?",
        ],
    )

    sql = Route(
        name=RouteName.SQL,
        utterances=[
            "I want to buy nike shoes that have 50% discount.",
            "Are there any shoes under Rs. 3000?",
            "Do you have formal shoes in size 9?",
            "Are there any Puma shoes on sale?",
            "What is the price of puma running shoes?",
            "Pink Puma shoes in price range 5000 to 1000",
        ],
    )

    small_talk = Route(
        name=RouteName.SMALL_TALK,
        utterances=[
            "How are you?",
            "What is your name?",
            "Are you a robot?",
            "What are you?",
            "What do you do?",
        ],
    )

    routes: List[Route] = [faq, sql, small_talk]
    return SemanticRouter(routes=routes, encoder=encoder, auto_sync="local")


#  Module-level instance (available to importers)
router = build_router()

if __name__ == "__main__":

    print(router("What is your policy on defective product?").name)
    print(router("Pink Puma shoes in price range 5000 to 1000").name)
    print(router("How are you?").name)

