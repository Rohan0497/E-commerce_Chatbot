"""
Streamlit entry-point for the E-commerce Bot.

Responsibilities
- Initialize FAQ vector store (idempotent)
- Route user queries via semantic router
- Call the appropriate handler (FAQ, SQL, or Small Talk)
- Render a simple chat interface
"""
from __future__ import annotations

import logging
import streamlit as st

from router import router, RouteName
from faq import ingest_faq_data, faq_chain
from sql import sql_chain
from smalltalk import talk
from config import FAQ_CSV_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    route = router(query).name
    if route == RouteName.FAQ:
        return faq_chain(query)
    if route == RouteName.SQL:
        return sql_chain(query)
    if route == RouteName.SMALL_TALK:
        return talk(query)
    return f"Route {route} not implemented yet."


def _one_time_ingestion() -> None:
    """Populate FAQ collection once (no-op if already present)."""
    try:
        ingest_faq_data(FAQ_CSV_PATH)
    except Exception as exc:  
        logger.exception("Failed to ingest FAQ data: %s", exc)


def main() -> None: 
    """Run the Streamlit chat UI."""
    st.title("E-commerce Bot")

    _one_time_ingestion()

    # In-memory chat transcript
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])  # type: ignore[arg-type]

    query = st.chat_input("Write your query")  # type: ignore[assignment]
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
