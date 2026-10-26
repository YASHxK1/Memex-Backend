from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from memex_backend.config import Settings
from memex_backend.main import create_app
from memex_backend.store import VectorStore


class FakeEmbedder:
    dimension = 3

    def __init__(self):
        self.document_calls = 0

    def embed_documents(self, texts):
        self.document_calls += 1
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    def embed_query(self, query):
        return [1.0, 1.0, 0.0]


def client_and_fakes():
    embedder = FakeEmbedder()
    settings = Settings(api_token="test-token", chunk_tokens=4, chunk_overlap=1)
    store = VectorStore(
        mode="embedded", collection="memex", vector_size=embedder.dimension,
        path=":memory:", url="http://localhost:6333", client=QdrantClient(":memory:"),
    )
    return TestClient(create_app(settings, embedder, store)), embedder, store


def auth():
    return {"Authorization": "Bearer test-token"}


def test_health_and_authentication():
    client, _, _ = client_and_fakes()
    assert client.get("/health").status_code == 200
    assert client.get("/v1/status").status_code == 401
    assert client.get("/v1/sources", headers={"Authorization": "Basic x"}).status_code == 401


def test_index_unchanged_update_sources_status_and_search():
    client, embedder, _ = client_and_fakes()
    body = {"path": "notes.md", "content": "# Topic\none two three", "hash": "h1"}
    first = client.post("/v1/documents", json=body, headers=auth())
    assert first.status_code == 200
    assert first.json() == {"status": "indexed", "chunks": 1}
    assert client.post("/v1/documents", json=body, headers=auth()).json() == {"status": "unchanged"}
    assert embedder.document_calls == 1
    updated = {**body, "content": "# Topic\nfour five", "hash": "h2"}
    client.post("/v1/documents", json=updated, headers=auth())
    assert client.get("/v1/sources", headers=auth()).json() == {"sources": [{"path": "notes.md", "chunks": 1}]}
    assert client.get("/v1/status", headers=auth()).json() == {
        "model": "Qwen/Qwen3-Embedding-0.6B", "vector_dimension": 3, "collection": "memex",
        "document_count": 1, "chunk_count": 1,
    }
    result = client.post("/v1/search", json={"query": "topic", "top_k": 5, "min_score": 0.3}, headers=auth())
    assert result.json()["results"][0]["path"] == "notes.md"
    assert client.post("/v1/search", json={"query": "topic", "top_k": 0}, headers=auth()).status_code == 422


def test_delete_and_reindex():
    client, _, store = client_and_fakes()
    body = {"path": "notes.txt", "content": "saved note", "hash": "h1"}
    client.post("/v1/documents", json=body, headers=auth())
    response = client.post("/v1/reindex", headers=auth())
    assert response.json() == {"status": "reindexed", "documents": 1}
    assert store.sources() == [{"path": "notes.txt", "chunks": 1}]
    assert client.delete("/v1/documents", params={"path": "notes.txt"}, headers=auth()).json() == {"status": "deleted"}
    assert store.counts() == (0, 0)
