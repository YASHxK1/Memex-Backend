from collections import Counter
import uuid

from qdrant_client import QdrantClient, models


class VectorStore:
    def __init__(self, mode: str, collection: str, vector_size: int, path, url: str, client=None) -> None:
        self.collection = collection
        self.vector_size = vector_size
        self.client = client or (
            QdrantClient(path=str(path))
            if mode == "embedded"
            else QdrantClient(url=url)
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=self.vector_size, distance=models.Distance.COSINE),
            )

    def _points(self, path: str | None = None):
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=models.Filter(
                    must=([models.FieldCondition(key="path", match=models.MatchValue(value=path))] if path else []),
                    must_not=[models.FieldCondition(key="kind", match=models.MatchValue(value="memory"))],
                ),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            yield from points
            if offset is None:
                break

    def document_hash(self, path: str) -> str | None:
        return next((point.payload.get("doc_hash") for point in self._points(path)), None)

    def upsert_document(self, path: str, content: str, doc_hash: str, chunks, vectors) -> None:
        self.delete_document(path)
        if not chunks:
            return
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"memex:{path}:{chunk.chunk_index}"))
            points.append(models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "path": path,
                    "heading": chunk.heading,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "doc_hash": doc_hash,
                    "document_content": content,
                },
            ))
        self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def delete_document(self, path: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(key="path", match=models.MatchValue(value=path))])
            ),
            wait=True,
        )

    def sources(self) -> list[dict]:
        counts = Counter(point.payload["path"] for point in self._points())
        return [{"path": path, "chunks": count} for path, count in sorted(counts.items())]

    def counts(self) -> tuple[int, int]:
        sources = self.sources()
        return len(sources), sum(source["chunks"] for source in sources)

    def search(self, vector: list[float], top_k: int, min_score: float) -> list[dict]:
        hits = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=models.Filter(must_not=[
                models.FieldCondition(key="kind", match=models.MatchValue(value="memory")),
            ]),
            limit=top_k,
            score_threshold=min_score,
            with_payload=True,
        ).points
        return [
            {
                "score": hit.score,
                "path": hit.payload["path"],
                "heading": hit.payload.get("heading"),
                "chunk_index": hit.payload["chunk_index"],
                "text": hit.payload["text"],
            }
            for hit in hits
        ]

    def add_memory(self, memory_id: str, text: str, vector: list[float], created_at: str,
                   updated_at: str | None = None) -> None:
        updated_at = updated_at or created_at
        self.client.upsert(
            collection_name=self.collection,
            points=[models.PointStruct(
                id=memory_id,
                vector=vector,
                payload={"kind": "memory", "memory_id": memory_id, "text": text,
                         "created_at": created_at, "updated_at": updated_at},
            )],
            wait=True,
        )

    def get_memory(self, memory_id: str) -> dict | None:
        points = self.client.retrieve(
            collection_name=self.collection, ids=[memory_id], with_payload=True, with_vectors=False,
        )
        if not points or points[0].payload.get("kind") != "memory":
            return None
        payload = points[0].payload
        return {"id": payload["memory_id"], "text": payload["text"],
                "created_at": payload["created_at"], "updated_at": payload["updated_at"]}

    def update_memory(self, memory_id: str, text: str, vector: list[float], timestamp: str) -> dict | None:
        existing = self.get_memory(memory_id)
        if existing is None:
            return None
        self.client.upsert(
            collection_name=self.collection,
            points=[models.PointStruct(
                id=memory_id,
                vector=vector,
                payload={"kind": "memory", "memory_id": memory_id, "text": text,
                         "created_at": existing["created_at"], "updated_at": timestamp},
            )],
            wait=True,
        )
        return {**existing, "text": text, "updated_at": timestamp}

    def delete_memory(self, memory_id: str) -> bool:
        if self.get_memory(memory_id) is None:
            return False
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.PointIdsList(points=[memory_id]),
            wait=True,
        )
        return True

    def memories(self) -> list[dict]:
        offset = None
        found = []
        memory_filter = models.Filter(must=[
            models.FieldCondition(key="kind", match=models.MatchValue(value="memory")),
        ])
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection, scroll_filter=memory_filter, limit=256,
                offset=offset, with_payload=True, with_vectors=False,
            )
            for point in points:
                payload = point.payload
                found.append({"id": payload["memory_id"], "text": payload["text"],
                              "created_at": payload["created_at"], "updated_at": payload["updated_at"]})
            if offset is None:
                break
        return found

    def search_memories(self, vector: list[float], top_k: int, min_score: float) -> list[dict]:
        hits = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=models.Filter(must=[
                models.FieldCondition(key="kind", match=models.MatchValue(value="memory")),
            ]),
            limit=top_k,
            score_threshold=min_score,
            with_payload=True,
        ).points
        return [{"id": hit.payload["memory_id"], "text": hit.payload["text"], "score": hit.score} for hit in hits]

    def documents(self) -> list[tuple[str, str, str]]:
        found: dict[str, tuple[str, str]] = {}
        for point in self._points():
            payload = point.payload
            found.setdefault(payload["path"], (payload["doc_hash"], payload["document_content"]))
        return [(path, doc_hash, content) for path, (doc_hash, content) in sorted(found.items())]

    def rebuild(self, vector_size: int) -> None:
        self.client.delete_collection(self.collection)
        self.vector_size = vector_size
        self._ensure_collection()
