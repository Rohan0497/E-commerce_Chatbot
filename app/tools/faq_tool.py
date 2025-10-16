"""FAQ search and answer tools wrapping ChromaDB + Groq usage."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import chromadb
from groq import Groq

from app.config import GROQ_MODEL_ENV, require_env

COLLECTION_NAME = "faqs"


def _build_chroma(client: Optional[chromadb.Client]) -> chromadb.Client:
    """Return a Chroma client, building one if not injected."""
    if client is not None:
        return client
    return chromadb.Client()


def _build_groq(client: Optional[Groq]) -> Groq:
    """Return a Groq client, building one if not injected."""
    if client is not None:
        return client
    return Groq()


def faq_search(
    query: str,
    k: int = 3,
    client: Optional[chromadb.Client] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve the top-k FAQ entries relevant to the query.

    Returns
    -------
    Dict[str, list[dict]]
        {"items": [{"question": str, "answer": str, "score": float}, ...]}
    """
    chroma = _build_chroma(client)
    collection = chroma.get_collection(name=COLLECTION_NAME)
    result = collection.query(query_texts=[query], n_results=k)

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    # Chroma may return either "distances" (smaller is better) or "scores" (larger is better).
    raw_scores = result.get("scores") or result.get("distances") or [[]]
    scores = raw_scores[0] if raw_scores else []

    items: List[Dict[str, Any]] = []
    for idx, question in enumerate(documents):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        raw_score = scores[idx] if idx < len(scores) else None

        if raw_score is None:
            score_value = 0.0
        else:
            # When working with distances we invert so that higher = better.
            score_value = float(raw_score)
            if result.get("distances") is not None:
                score_value = max(0.0, 1.0 - float(raw_score))

        items.append(
            {
                "question": question,
                "answer": metadata.get("answer", ""),
                "score": score_value,
            }
        )

    return {"items": items}


def faq_answer(
    question: str,
    context: List[Dict[str, Any]],
    model: Optional[str] = None,
    client: Optional[Groq] = None,
) -> Dict[str, str]:
    """
    Generate an answer using only the provided context snippets.

    Parameters
    ----------
    question : str
        User's natural language question.
    context : list[dict]
        List of context dictionaries (expects `answer` values).
    model : Optional[str]
        Groq model override, falls back to env var.
    client : Optional[Groq]
        Injected Groq client for testability.

    Returns
    -------
    Dict[str, str]
        {"text": "answer string"}
    """
    groq_client = _build_groq(client)
    resolved_model = model or require_env(GROQ_MODEL_ENV)

    context_blob = " ".join(str(item.get("answer", "")) for item in context if item)
    prompt = (
        "Given the following context and question, generate an answer based on this context only.\n"
        "If the answer is not found in the context, state: I don't know.\n\n"
        f"Question: {question}\n"
        f"Context: {context_blob}\n"
    )
    completion = groq_client.chat.completions.create(
        model=resolved_model,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = completion.choices[0].message.content
    return {"text": answer}
