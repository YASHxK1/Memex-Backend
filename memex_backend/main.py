from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from .auth import require_bearer_token
from .chunker import chunk_document
from .config import Settings, get_settings
from .embedder import Embedder
from .schemas import (DocumentIn, DocumentResult, MemoryIn, MemoryOut, MemorySearchIn,
                      MemorySearchOut, SearchIn, SearchOut, SourcesOut, StatusOut)
from .store import VectorStore


def create_app(settings: Settings | None = None, embedder=None, store=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_settings = settings or get_settings()
        app.state.settings = active_settings
        active_embedder = embedder or Embedder(active_settings.embed_model, active_settings.device)
        active_store = store or VectorStore(
            mode=active_settings.qdrant_mode,
            collection=active_settings.collection,
            vector_size=active_embedder.dimension,
            path=active_settings.resolved_qdrant_path,
            url=active_settings.qdrant_url,
        )
        app.state.embedder, app.state.store = active_embedder, active_store
        yield

    app = FastAPI(title="Memex Backend", version="0.1.0", lifespan=lifespan)
    protected = [Depends(require_bearer_token)]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/status", response_model=StatusOut, dependencies=protected)
    def status(request: Request):
        documents, chunks = request.app.state.store.counts()
        active_settings = request.app.state.settings
        return {
            "model": active_settings.embed_model,
            "vector_dimension": request.app.state.embedder.dimension,
            "collection": active_settings.collection,
            "document_count": documents,
            "chunk_count": chunks,
        }

    @app.post("/v1/documents", response_model=DocumentResult, dependencies=protected)
    def index_document(body: DocumentIn, request: Request):
        store = request.app.state.store
        if store.document_hash(body.path) == body.hash:
            return {"status": "unchanged"}
        active_settings = request.app.state.settings
        chunks = chunk_document(body.path, body.content, active_settings.chunk_tokens, active_settings.chunk_overlap)
        vectors = request.app.state.embedder.embed_documents([chunk.text for chunk in chunks])
        store.upsert_document(body.path, body.content, body.hash, chunks, vectors)
        return {"status": "indexed", "chunks": len(chunks)}

    @app.delete("/v1/documents", dependencies=protected)
    def delete_document(request: Request, path: str = Query(min_length=1)):
        request.app.state.store.delete_document(path)
        return {"status": "deleted"}

    @app.get("/v1/sources", response_model=SourcesOut, dependencies=protected)
    def sources(request: Request):
        return {"sources": request.app.state.store.sources()}

    @app.post("/v1/search", response_model=SearchOut, dependencies=protected)
    def search(body: SearchIn, request: Request):
        vector = request.app.state.embedder.embed_query(body.query)
        return {"results": request.app.state.store.search(vector, body.top_k, body.min_score)}

    @app.post("/v1/memories", response_model=MemoryOut, status_code=201, dependencies=protected)
    def add_memory(body: MemoryIn, request: Request):
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        vector = request.app.state.embedder.embed_query(body.text)
        request.app.state.store.add_memory(memory_id, body.text, vector, timestamp)
        return {"id": memory_id, "text": body.text, "created_at": timestamp, "updated_at": timestamp}

    @app.get("/v1/memories/{memory_id}", response_model=MemoryOut, dependencies=protected)
    def get_memory(memory_id: uuid.UUID, request: Request):
        result = request.app.state.store.get_memory(str(memory_id))
        if result is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        return result

    @app.put("/v1/memories/{memory_id}", response_model=MemoryOut, dependencies=protected)
    def update_memory(memory_id: uuid.UUID, body: MemoryIn, request: Request):
        memory_id = str(memory_id)
        if request.app.state.store.get_memory(memory_id) is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        timestamp = datetime.now(timezone.utc).isoformat()
        vector = request.app.state.embedder.embed_query(body.text)
        result = request.app.state.store.update_memory(memory_id, body.text, vector, timestamp)
        if result is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        return result

    @app.delete("/v1/memories/{memory_id}", dependencies=protected)
    def delete_memory(memory_id: uuid.UUID, request: Request):
        if not request.app.state.store.delete_memory(str(memory_id)):
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"status": "deleted"}

    @app.post("/v1/memories/search", response_model=MemorySearchOut, dependencies=protected)
    def search_memories(body: MemorySearchIn, request: Request):
        vector = request.app.state.embedder.embed_query(body.query)
        return {"results": request.app.state.store.search_memories(vector, body.top_k, body.min_score)}

    @app.post("/v1/reindex", dependencies=protected)
    def reindex(request: Request):
        store, current_embedder = request.app.state.store, request.app.state.embedder
        active_settings = request.app.state.settings
        documents = store.documents()
        memories = store.memories()
        store.rebuild(current_embedder.dimension)
        for path, doc_hash, content in documents:
            chunks = chunk_document(path, content, active_settings.chunk_tokens, active_settings.chunk_overlap)
            vectors = current_embedder.embed_documents([chunk.text for chunk in chunks])
            store.upsert_document(path, content, doc_hash, chunks, vectors)
        for memory in memories:
            vector = current_embedder.embed_query(memory["text"])
            store.add_memory(memory["id"], memory["text"], vector,
                             memory["created_at"], memory["updated_at"])
        return {"status": "reindexed", "documents": len(documents)}

    return app


app = create_app()
