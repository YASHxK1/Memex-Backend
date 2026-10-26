# Architecture and Request Flows

## Components

| Component | Responsibility |
|---|---|
| `memex_backend/main.py` | Creates the FastAPI application, initializes runtime dependencies, and handles HTTP routes. |
| `memex_backend/config.py` | Loads and validates `MEMEX_*` settings from environment variables and `.env`. |
| `memex_backend/auth.py` | Validates the Bearer token for protected routes. |
| `memex_backend/schemas.py` | Defines request and response validation with Pydantic. |
| `memex_backend/chunker.py` | Splits Markdown sections or text paragraphs into overlapping chunks. |
| `memex_backend/embedder.py` | Lazily loads the configured Sentence Transformers model and produces vectors. |
| `memex_backend/store.py` | Maps documents and chunks to Qdrant points and implements search and collection operations. |

FastAPI lifespan initialization loads settings, constructs the embedder, asks it for the vector dimension, and opens or creates the Qdrant collection. The model is loaded lazily by Sentence Transformers when its dimension or embeddings are first requested. For normal service startup, collection initialization therefore requires model availability.

`create_app(settings, embedder, store)` supports dependency injection. Tests pass explicit settings and fake embeddings; the API tests use a Qdrant `:memory:` client so they avoid persistent data and model downloads.

## Index flow

1. A client sends `POST /v1/documents` with a path, content, and content hash.
2. The backend looks up an existing point for that path. If its stored hash matches, the route returns `unchanged` without chunking or embedding.
3. The chunker splits content based on file suffix and heading structure, applying the configured size and overlap.
4. The embedder encodes each chunk and normalizes vectors.
5. The store deletes existing points for the path and upserts new points with deterministic IDs and payloads.

The submitted hash is trusted as the document version identifier; the backend does not recompute it. Clients should send a stable content hash, such as a SHA-256 digest, and change it whenever content changes.

## Search flow

1. A client sends a query, optional `top_k`, and optional `min_score` to `POST /v1/search`.
2. The embedder encodes the query, using `encode_query` when exposed by the loaded model.
3. Qdrant runs cosine similarity search with the score threshold and result limit.
4. The API returns score, source path, heading, chunk index, and chunk text for each hit.

The same configured model must be used for document and query vectors. If the embedding model changes, call `POST /v1/reindex` after configuring the new model.

## Runtime boundaries

- Embedded mode stores Qdrant data in the configured local directory. Server mode connects to `MEMEX_QDRANT_URL`.
- Embeddings are computed in the service process. Model weights may be downloaded on first use; after download, inference is local.
- The service has one token and one collection. It does not currently provide user-level authorization or per-source collection isolation.
- Deploy behind HTTPS before accepting traffic from outside a trusted local environment.
