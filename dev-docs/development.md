# Development and Tests

## Local setup

Install the project and development dependencies:

```bash
python -m pip install -e '.[dev]'
```

The test dependencies include pytest and HTTPX. Runtime dependencies include FastAPI, Pydantic Settings, Qdrant Client, Sentence Transformers, and Transformers. Tests do not load embedding model weights.

## Run checks

```bash
pytest
python -m compileall -q memex_backend tests
```

The chunker tests cover heading context, size splitting and overlap, text paragraphs, and empty input. API tests run the app through FastAPI's test client with a fake embedder and an in-memory Qdrant collection. They cover public health, protected routes, hash-based no-op indexing, document replacement, status/source counts, search, validation, deletion, and reindex.

## Adding or changing an API route

1. Define or update Pydantic request/response models in `schemas.py`.
2. Add the route in `main.py`; protect every `/v1/*` route with `Depends(require_bearer_token)`.
3. Keep embedding and persistence details behind the embedder/store methods where possible.
4. Add an API test for success, validation, authentication, and the relevant state transition.
5. Update `api.md` and, if behavior/configuration changes, the related developer guide page and root README.

## Dependency injection in tests

Use `create_app(settings, embedder, store)` to provide a deterministic fake embedder and isolated store. The existing API suite supplies a real Qdrant `QdrantClient(":memory:")`, so it exercises storage filters, payloads, point writes, and vector search without persistent state. Keep test tokens synthetic and never use a production token in tests.

## Design constraints to preserve

- Document and query embeddings must come from the same model and vector dimension.
- Hash matches must avoid unnecessary re-embedding.
- Source path is the document identity for replacement and deletion.
- Reindex must preserve original content and stored hashes while rebuilding vectors.
- Search responses should expose chunk provenance (`path`, `heading`, and `chunk_index`) with text and score.
- Keep tests independent of external Qdrant servers and model downloads.
