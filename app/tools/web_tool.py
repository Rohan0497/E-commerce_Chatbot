"""Placeholder web search tool for future expansion."""

from __future__ import annotations

from typing import Any, Dict, List


def web_search(q: str, top_k: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """
    Stub implementation that returns no live results.

    Returns
    -------
    Dict[str, list[dict]]
        {"results": []}
    """
    # Real implementation can be wired later (e.g. external API call).
    return {"results": []}
