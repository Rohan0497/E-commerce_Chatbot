"""Session memory helpers for storing user preferences and context."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - streamlit absent in tests
    st = None

_fallback_store: Dict[str, Any] = {}


def _get_store() -> Dict[str, Any]:
    """Return the active memory backing store (Streamlit session or fallback)."""
    if st is not None and hasattr(st, "session_state"):
        return st.session_state.setdefault("agent_memory", {})
    return _fallback_store


def memory_get(keys: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch a subset of memory items."""
    store = _get_store()
    return {"memory": {key: store.get(key) for key in keys}}


def memory_set(pairs: Dict[str, Any]) -> Dict[str, bool]:
    """Persist preference key/value pairs."""
    store = _get_store()
    store.update(pairs)
    return {"ok": True}
