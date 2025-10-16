"""
FAQ ingestion and retrieval with ChromaDB + Groq answer synthesis.

Design
- Idempotent ingestion (no duplicate writes)
- Simple top-k retrieval to form context
- LLM answer constrained to provided context
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import chromadb
import pandas as pd
from dotenv import load_dotenv
from groq import Groq

from .config import FAQ_CSV_PATH, GROQ_MODEL_ENV, require_env

load_dotenv()

COLLECTION_NAME = "faqs"


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
    if client is None:
        client = chromadb.Client()
    collection = client.get_collection(name=COLLECTION_NAME)
    return collection.query(query_texts=[query], n_results=n_results)


def generate_answer(query: str, context: str, client: Optional[Groq] = None, model: Optional[str] = None) -> str:
    """
    Answer user's question strictly from provided context.

    Returns
    -------
    str
        LLM response (or "I don't know" when not in context).
    """
    if client is None:
        client = _client()
    if model is None:
        model = require_env(GROQ_MODEL_ENV)

    prompt = (
        "Given the following context and question, generate an answer based on this context only.\n"
        "If the answer is not found in the context, state: I don't know.\n\n"
        f"Question: {query}\n"
        f"Context: {context}\n"
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content  # type: ignore[no-any-return]


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
    result = get_relevant_qa(query, client=chroma_client)
    # Concatenate answers from top-k matched questions to form context.
    context = " ".join([r.get("answer", "") for r in result["metadatas"][0]])
    return generate_answer(query, context, client=groq_client, model=model)
