"""
Small-talk handler using Groq chat completions.

Design
- Dependency injection for Groq client and model name.
- Simple, safe prompt.
"""
from __future__ import annotations

from typing import Optional
from dotenv import load_dotenv
from groq import Groq

from config import GROQ_MODEL_ENV, require_env

# Load env early so tests and runtime share behavior
load_dotenv()


def _client() -> Groq:
    """Build and return a Groq client (can be mocked)."""
    return Groq()


def talk(query: str, client: Optional[Groq] = None, model: Optional[str] = None) -> str:
    """
    Generate a small-talk response.

    Parameters
    ----------
    query : str
        The user's small-talk query.
    client : Optional[Groq], default None
        Injected Groq client for testability. Built if not provided.
    model : Optional[str], default None
        Override for model name; falls back to the GROQ_MODEL env var.

    Returns
    -------
    str
        Assistant message content.
    """
    if client is None:
        client = _client()
    if model is None:
        model = require_env(GROQ_MODEL_ENV)

    prompt = (
        "You are a helpful and friendly chatbot for small talk. "
        "You can answer questions about the weather, your name, your purpose, and more.\n"
        f"Question: {query}"
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content  # type: ignore[no-any-return]
