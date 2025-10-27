"""Shared helpers for building Chroma clients with consistent settings."""

from __future__ import annotations

import os
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

_CLIENT: Optional[chromadb.Client] = None


def get_chroma_client() -> chromadb.Client:
    """
    Return a cached Chroma client configured according to environment settings.

    - When `CHROMA_PATH` is set, a persistent client is used so FAQ data survives restarts.
    - Otherwise an in-memory client is created with `allow_reset=True` for test friendliness.
    """
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    chroma_path = os.getenv("CHROMA_PATH")
    if chroma_path:
        client = chromadb.PersistentClient(path=chroma_path)
    else:
        client = chromadb.Client(settings=ChromaSettings(allow_reset=True))

    _CLIENT = client
    return client


def reset_chroma_client() -> None:
    """Clear the cached Chroma client (useful in tests)."""
    global _CLIENT
    _CLIENT = None
