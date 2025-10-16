import types
import pandas as pd
from pathlib import Path

from app.faq import ingest_faq_data, get_relevant_qa, faq_chain, generate_answer
from tests.conftest import DummyGroq


class DummyCollection:
    def __init__(self):
        self.docs = []
        self.metadatas = []
        self.ids = []

    def add(self, documents, metadatas, ids):
        self.docs.extend(documents)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)

    def query(self, query_texts, n_results=2):
        # Return first n_results entries deterministically
        metas = self.metadatas[:n_results]
        return {"metadatas": [metas]}


class DummyClient:
    def __init__(self):
        self._collections = {}

    def list_collections(self):
        return [types.SimpleNamespace(name=n) for n in self._collections]

    def get_or_create_collection(self, name):
        col = self._collections.get(name) or DummyCollection()
        self._collections[name] = col
        return col

    def get_collection(self, name):
        return self._collections[name]


def test_ingest_and_retrieve(tmp_path: Path):
    # Create a small csv
    csv = tmp_path / "faq.csv"
    df = pd.DataFrame({"question": ["Q1", "Q2"], "answer": ["A1", "A2"]})
    df.to_csv(csv, index=False)

    client = DummyClient()
    ingest_faq_data(csv, client=client)
    result = get_relevant_qa("anything", client=client, n_results=2)
    assert len(result["metadatas"][0]) == 2


def test_faq_chain_with_groq_mock():
    # Build fake chroma result
    class FakeClient(DummyClient):
        def __init__(self):
            super().__init__()
            col = self.get_or_create_collection("faqs")
            col.add(["Q1", "Q2"], [{"answer": "A1"}, {"answer": "A2"}], ["id_0", "id_1"])

    chroma = FakeClient()
    groq_client = DummyGroq("A1")  # Always returns "A1"
    out = faq_chain("What is X?", chroma_client=chroma, groq_client=groq_client, model="dummy")
    assert out == "A1"


def test_generate_answer_simple():
    out = generate_answer("Q", "C", client=DummyGroq("ANS"), model="dummy")
    assert out == "ANS"
