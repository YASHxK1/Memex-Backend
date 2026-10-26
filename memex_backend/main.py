from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request

from .auth import require_bearer_token
from .chunker import chunk_document
from .config import Settings, get_settings
from .embedder import Embedder
from .schemas import DocumentIn, DocumentResult, SearchIn, SearchOut, SourcesOut, StatusOut
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

    @app.post("/v1/reindex", dependencies=protected)
    def reindex(request: Request):
        store, current_embedder = request.app.state.store, request.app.state.embedder
        active_settings = request.app.state.settings
        documents = store.documents()
        store.rebuild(current_embedder.dimension)
        for path, doc_hash, content in documents:
            chunks = chunk_document(path, content, active_settings.chunk_tokens, active_settings.chunk_overlap)
            vectors = current_embedder.embed_documents([chunk.text for chunk in chunks])
            store.upsert_document(path, content, doc_hash, chunks, vectors)
        return {"status": "reindexed", "documents": len(documents)}

    return app


app = create_app()
