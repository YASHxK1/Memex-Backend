# Configuration and Operations

## Settings

Settings use the `MEMEX_` prefix and are read from the process environment or a `.env` file in the working directory. Environment values take precedence over `.env` values. Unknown settings are ignored.

| Variable | Default | Meaning |
|---|---|---|
| `MEMEX_API_TOKEN` | Required | Shared secret required by all `/v1/*` routes. |
| `MEMEX_EMBED_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | Sentence Transformers model used for both document and query embeddings. |
| `MEMEX_DEVICE` | `auto` | Device selection: `auto`, `cpu`, `cuda`, or `mps`. |
| `MEMEX_QDRANT_MODE` | `embedded` | `embedded` for local persistent Qdrant or `server` for a Qdrant URL. |
| `MEMEX_QDRANT_PATH` | `~/.memex-backend/qdrant` | Embedded Qdrant data directory; `~` is expanded. |
| `MEMEX_QDRANT_URL` | `http://localhost:6333` | Qdrant server endpoint in server mode. |
| `MEMEX_COLLECTION` | `memex` | Collection name. |
| `MEMEX_CHUNK_TOKENS` | `512` | Maximum whitespace-delimited units per chunk. |
| `MEMEX_CHUNK_OVERLAP` | `64` | Number of whitespace-delimited units repeated across chunk boundaries. |

Validation rejects unsupported mode/device values, non-positive chunk size, negative overlap, and overlap greater than or equal to chunk size.

Example local `.env`:

```dotenv
MEMEX_API_TOKEN=replace-with-a-long-random-secret
MEMEX_QDRANT_MODE=embedded
MEMEX_QDRANT_PATH=~/.memex-backend/qdrant
```

## Installation and startup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export MEMEX_API_TOKEN='replace-with-a-long-random-secret'
uvicorn memex_backend.main:app --host 127.0.0.1 --port 8000
```

`sentence-transformers` loads the configured model when the service initializes its vector size. Initial setup may download model weights. GPU is optional for the default model; larger model variants require suitable memory and are better suited to GPU-backed hosts.

For server mode, start or configure Qdrant separately, then set `MEMEX_QDRANT_MODE=server` and `MEMEX_QDRANT_URL`. Embedded and server modes point to different storage locations; choose the correct mode and path/URL when starting the process.

## Health and deployment

- Use `GET /health` for process liveness. It does not verify model or Qdrant readiness.
- Use authenticated `GET /v1/status` to inspect the selected model, vector dimension, collection name, and stored counts.
- Keep the token secret and transmit it only over HTTPS outside trusted local development.
- Persist and back up the embedded Qdrant directory, or back up the Qdrant server storage according to that deployment's operational policy.
- Avoid running multiple local embedded clients against the same storage path concurrently. For multiple service processes, use Qdrant server mode.
- Reindex after changing the embedding model or chunk size/overlap. Keep the current content in Qdrant until reindex can capture it; the backend stores source content in point payloads for this purpose.

## Troubleshooting

| Symptom | Check |
|---|---|
| Startup says `MEMEX_API_TOKEN` is missing | Set the variable or add it to `.env` in the service working directory. |
| `401` from a `/v1/*` route | Send `Authorization: Bearer <token>` and verify the configured token has no accidental whitespace. |
| Qdrant connection error | Check `MEMEX_QDRANT_MODE`, server URL/reachability, or embedded path permissions. |
| Vector dimension mismatch after switching models | Call `POST /v1/reindex` with the new model active. |
| Empty search results | Confirm the collection contains chunks, lower `min_score`, and verify documents and queries use the same model. |
| Slow initial startup or indexing | The model may be loading/downloading or running on CPU; inspect available memory/device and model size. |
