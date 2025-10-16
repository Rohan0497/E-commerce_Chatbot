"""
Streamlit entry-point for the E-commerce Bot.

Responsibilities
- Initialize FAQ vector store (idempotent)
- Route user queries (small-talk vs agent)
- Invoke the agent loop with configured tools
- Render a simple chat interface and handle clarifications
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import streamlit as st

# Ensure absolute `app.*` imports work even when Streamlit sets cwd to app/
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agent import Agent
from app.config import FAQ_CSV_PATH
from app.faq import ingest_faq_data
from app.smalltalk import talk
from app.tools import ToolSpec
from app.tools.faq_tool import faq_search, faq_answer
from app.tools.sql_tool import sql_generate, sql_run, verbalize
from app.tools.memory import memory_get, memory_set
from app.tools.web_tool import web_search

try:
    from app.router import router, RouteName
except ImportError:  # pragma: no cover - optional dependency
    router = None
    RouteName = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tool registry assembly
# --------------------------------------------------------------------------- #

def _faq_search_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return faq_search(**args)


def _faq_answer_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return faq_answer(**args)


def _sql_generate_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return sql_generate(**args)


def _sql_run_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return sql_run(**args)


def _verbalize_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return verbalize(**args)


def _web_search_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return web_search(**args)


def _build_tool_registry() -> Dict[str, ToolSpec]:
    return {
        "faq_search": ToolSpec(name="faq_search", fn=_faq_search_tool),
        "faq_answer": ToolSpec(name="faq_answer", fn=_faq_answer_tool),
        "sql_generate": ToolSpec(name="sql_generate", fn=_sql_generate_tool),
        "sql_run": ToolSpec(name="sql_run", fn=_sql_run_tool),
        "verbalize": ToolSpec(name="verbalize", fn=_verbalize_tool),
        "web_search": ToolSpec(name="web_search", fn=_web_search_tool),
    }


def _get_agent() -> Agent:
    if "agent_instance" not in st.session_state:
        st.session_state["agent_instance"] = Agent(tools=_build_tool_registry())
    return st.session_state["agent_instance"]


def _load_memory() -> Dict[str, Any]:
    snapshot = memory_get(["brand", "price_ceiling"])
    return snapshot.get("memory", {})


def _persist_memory(updates: Dict[str, Any]) -> None:
    if not updates:
        return
    memory_set(updates)


def _needs_small_talk(query: str) -> bool:
    if router and RouteName:
        try:
            return router(query).name == RouteName.SMALL_TALK
        except Exception:  # pragma: no cover - router fallback
            logger.exception("Router failed, falling back to heuristics.")
    lowered = query.lower()
    smalltalk_keywords = {"how are you", "hello", "hi", "who are you", "what's up"}
    return any(keyword in lowered for keyword in smalltalk_keywords)


def ask(query: str) -> str:
    """
    Route a query to the appropriate handler and return the response.

    Parameters
    ----------
    query : str
        User's free-text question.

    Returns
    -------
    str
        Assistant answer string.
    """
    if _needs_small_talk(query):
        st.session_state.pop("agent_pending_clarification", None)
        response = talk(query)
        return f"{response}\nTrace: small_talk"

    agent = _get_agent()
    memory_snapshot = _load_memory()
    result = agent.run(query, memory_snapshot)

    _persist_memory(result.get("memory_updates", {}))

    if result.get("plan", {}).get("needs_clarification"):
        st.session_state["agent_pending_clarification"] = result["plan"]["needs_clarification"]
    else:
        st.session_state.pop("agent_pending_clarification", None)

    # Optionally stash last trace for debugging or future UI features
    st.session_state["agent_last_trace"] = result.get("trace", [])

    return result["text"]


def _one_time_ingestion() -> None:
    """Populate FAQ collection once (no-op if already present)."""
    try:
        ingest_faq_data(FAQ_CSV_PATH)
    except Exception as exc:  # pragma: no cover - startup guard
        logger.exception("Failed to ingest FAQ data: %s", exc)


def main() -> None:
    """Run the Streamlit chat UI."""
    st.title("E-commerce Bot")

    _one_time_ingestion()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])  # type: ignore[arg-type]

    placeholder = "Provide the missing details..." if st.session_state.get("agent_pending_clarification") else "Write your query"
    query = st.chat_input(placeholder)  # type: ignore[assignment]
    if not query:
        return

    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.messages.append({"role": "user", "content": query})

    try:
        response = ask(query)
    except Exception as exc:
        logger.exception("Error while handling query: %s", exc)
        response = "Sorry, something went wrong while handling your request."

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
