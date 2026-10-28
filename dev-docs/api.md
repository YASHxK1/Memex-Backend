# HTTP API Reference

Base URL is the address where Uvicorn is listening (default example: `http://localhost:8000`). JSON request bodies use `Content-Type: application/json`.

## Authentication

All `/v1/*` routes require:

```http
Authorization: Bearer <MEMEX_API_TOKEN>
```

Missing or invalid credentials return `401` with a Bearer authentication challenge. `/health` does not require a token.

## Routes

### `GET /health`

Public liveness check.

```json
{"status":"ok"}
```

### `GET /v1/status`

Returns active model and collection information plus counts:

```json
{
  "model": "Qwen/Qwen3-Embedding-0.6B",
  "vector_dimension": 1024,
  "collection": "memex",
  "document_count": 1,
  "chunk_count": 3
}
```

The dimension is obtained from the loaded model. Document count is the number of paths represented by stored points; a document producing zero chunks has no stored point and is not counted.

### `POST /v1/documents`

Index or replace a document.

```json
{
  "path": "notes/design.md",
  "content": "# Design\nThe system ...",
  "hash": "sha256:..."
}
```

Successful responses:

```json
{"status":"indexed","chunks":2}
```

If the existing path has the same submitted hash, the backend returns:

```json
{"status":"unchanged"}
```

`path` and `hash` must be non-empty strings. Empty content is accepted and results in zero chunks; because there are no points to store, it does not create a source entry. Chunk size and overlap are service configuration, not request fields.

### `DELETE /v1/documents?path=notes/design.md`

Deletes all points whose payload path exactly matches the supplied non-empty path. Returns:

```json
{"status":"deleted"}
```

Deleting an unknown path is successful and idempotent.

### `GET /v1/sources`

Lists paths represented in Qdrant and their chunk counts:

```json
{
  "sources": [
    {"path":"notes/design.md","chunks":2}
  ]
}
```

### `POST /v1/search`

Request:

```json
{"query":"How does indexing work?","top_k":5,"min_score":0.3}
```

`query` must be non-empty. `top_k` defaults to `5` and must be between `1` and `100`. `min_score` defaults to `0.0` and must be between `0.0` and `1.0`.

Response:

```json
{
  "results": [
    {
      "score": 0.81,
      "path": "notes/design.md",
      "heading": "Indexing",
      "chunk_index": 0,
      "text": "The system ..."
    }
  ]
}
```

An empty result set is returned when no points meet the threshold.

### Memory endpoints

Memories are single semantic records stored separately from indexed document chunks. All routes below require the same Bearer token as other `/v1/*` routes.

`POST /v1/memories` creates a memory from `{"text":"..."}` and returns its UUID, text, and UTC `created_at` / `updated_at` timestamps. `GET /v1/memories/{id}` retrieves it. `PUT /v1/memories/{id}` replaces its text and refreshes its embedding while preserving its ID and creation time. `DELETE /v1/memories/{id}` deletes it. Missing IDs return `404`; malformed UUIDs and invalid or empty text return `422`.

`POST /v1/memories/search` accepts the same `query`, `top_k`, and `min_score` fields as document search and returns matching memory IDs, text, and scores. Memory search and document search are isolated from one another. Reindexing preserves memories and re-embeds them with the active model.

### `POST /v1/reindex`

Rebuilds the configured collection using stored document content, the currently configured embedding model, and current chunking settings. This is required after changing embedding models and is also how chunking setting changes are applied to existing documents.

```json
{"status":"reindexed","documents":12}
```

Reindex reads each unique document path and its stored hash/content before deleting and recreating the collection, then chunks and embeds each document again. It is a synchronous operation; large collections can take time and consume memory/model compute.

## Validation and errors

Malformed JSON, missing required fields, invalid numeric bounds, and empty required strings are rejected by FastAPI/Pydantic with `422`. Infrastructure or model failures are not converted to custom API error shapes and surface as server errors in the standard FastAPI manner.
