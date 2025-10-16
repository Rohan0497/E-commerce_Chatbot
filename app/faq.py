"""
FAQ ingestion and retrieval with ChromaDB + Groq answer synthesis.

Design
- Idempotent ingestion (no duplicate writes)
- Simple top-k retrieval to form context
- LLM answer constrained to provided context
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any

import chromadb
import pandas as pd
from dotenv import load_dotenv
from groq import Groq

from app.config import FAQ_CSV_PATH, GROQ_MODEL_ENV, require_env
from app.tools import faq_tool

load_dotenv()

COLLECTION_NAME = faq_tool.COLLECTION_NAME


def _client() -> Groq:
    """Return a Groq client (mockable)."""
    return Groq()


def ingest_faq_data(path: Path, client: Optional[chromadb.Client] = None) -> None:
    """
    Load FAQ CSV into ChromaDB (idempotent).

    Parameters
    ----------
    path : Path
        CSV file with 'question', 'answer' columns.
    client : Optional[chromadb.Client]
        Injected Chroma client for testability.
    """
    if client is None:
        client = chromadb.Client()

    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        return  # Skip: already exists

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    df = pd.read_csv(path)
    docs = df["question"].astype(str).tolist()
    metadata = [{"answer": ans} for ans in df["answer"].astype(str).tolist()]
    ids = [f"id_{i}" for i in range(len(docs))]
    collection.add(documents=docs, metadatas=metadata, ids=ids)


def get_relevant_qa(query: str, client: Optional[chromadb.Client] = None, n_results: int = 2):
    """
    Query the FAQ collection for the most relevant entries.

    Returns
    -------
    Dict
        Chroma-like query result with top-k metadatas.
    """
    items = faq_tool.faq_search(query, k=n_results, client=client)["items"]
    metadatas = [{"answer": item.get("answer", "")} for item in items]
    return {"metadatas": [metadatas]}


def generate_answer(query: str, context: str, client: Optional[Groq] = None, model: Optional[str] = None) -> str:
    """
    Answer user's question strictly from provided context.

    Returns
    -------
    str
        LLM response (or "I don't know" when not in context).
    """
    context_items: List[Dict[str, Any]] = [{"answer": context}]
    result = faq_tool.faq_answer(
        question=query,
        context=context_items,
        model=model or require_env(GROQ_MODEL_ENV),
        client=client or _client(),
    )
    return result["text"]


def faq_chain(
    query: str,
    chroma_client: Optional[chromadb.Client] = None,
    groq_client: Optional[Groq] = None,
    model: Optional[str] = None,
) -> str:
    """
    Retrieve top-k FAQ entries and produce a concise answer.

    Strategy
    --------
    - Concatenate the 'answer' fields of the top-k entries into a single context blob.
    - Ask LLM to answer strictly from that context.
    """
    search = faq_tool.faq_search(query, k=2, client=chroma_client)
    context_items = [{"answer": item.get("answer", "")} for item in search["items"]]
    answer = faq_tool.faq_answer(
        question=query,
        context=context_items,
        model=model or require_env(GROQ_MODEL_ENV),
        client=groq_client or _client(),
    )
    return answer["text"]
