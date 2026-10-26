
-------
# Memex-backend

The self-hosted service behind **Memex**. It receives Markdown/text notes from [Memex-CLI](./README-frontend.md), chunks them, embeds them with **Qwen3-Embedding**, stores the vectors in **Qdrant**, and answers semantic search queries.

---

## Architecture

```
Memex-CLI ──HTTPS + Bearer token──► FastAPI
                                       │
              ┌────────────────────────┼─────────────────────────┐
              ▼                        ▼                         ▼
          Chunker              Qwen3-Embedding               Qdrant
     (markdown-aware)       (sentence-transformers)     (vectors + payload)
```

**Index flow:** receive file → hash check → chunk → embed → upsert to Qdrant.
**Search flow:** embed query (with query prompt) → Qdrant cosine search → return top-k chunks.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| API framework | FastAPI + Uvicorn |
| Embedding model | Qwen3-Embedding (default `0.6B`, optional `4B`/`8B`) via `sentence-transformers` |
| Vector database | Qdrant (embedded mode or server) |
| Validation | Pydantic |
| Testing | pytest |

> Indexing and searching must use the same embedding model. Changing models requires `POST /v1/reindex`.

## Installation

```bash
git clone https://github.com/<your-username>/Memex-backend.git
cd Memex-backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires `sentence-transformers>=2.7` and `transformers>=4.51`. A GPU is optional for the 0.6B model and recommended for 4B/8B.

### Qdrant

```bash
# Option A: embedded mode (default), data in ~/.memex-backend/qdrant

# Option B: Docker server
docker run -d -p 6333:6333 -v ~/.memex-backend/qdrant:/qdrant/storage qdrant/qdrant
```

## Running

```bash
export MEMEX_API_TOKEN="choose-a-long-random-secret"
uvicorn memex_backend.main:app --host 0.0.0.0 --port 8000
```

Use the same token when running `memex login` in the CLI. Put the service behind HTTPS (reverse proxy) before exposing it beyond localhost.

## API

All routes except `/health` require `Authorization: Bearer <token>`.

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/v1/status` | Model name, vector dimension, collection and chunk counts |
| `POST` | `/v1/documents` | Index or update a document (`path`, `content`, `hash`) |
| `DELETE` | `/v1/documents?path=...` | Delete a document and its vectors |
| `GET` | `/v1/sources` | List indexed documents with chunk counts |
| `POST` | `/v1/search` | Semantic search |
| `POST` | `/v1/reindex` | Rebuild the collection from stored content |

### Search

```http
POST /v1/search
{ "query": "what is memex", "top_k": 5, "min_score": 0.3 }
```

```json
{
  "results": [
    {
      "score": 0.81,
      "path": "notes/memex-design.md",
      "heading": "Tech stack",
      "chunk_index": 3,
      "text": "Memex uses Qwen3-Embedding for vectors and Qdrant for storage..."
    }
  ]
}
```

### Index a document

```http
POST /v1/documents
{ "path": "notes/memex-design.md", "hash": "sha256:...", "content": "# Memex ..." }
```

If the stored hash matches, the backend skips re-embedding and returns `{"status": "unchanged"}`.

## Configuration

Environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `MEMEX_API_TOKEN` | required | Bearer token clients must send |
| `MEMEX_EMBED_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | Embedding model |
| `MEMEX_DEVICE` | `auto` | `auto`, `cpu`, `cuda`, `mps` |
| `MEMEX_QDRANT_MODE` | `embedded` | `embedded` or `server` |
| `MEMEX_QDRANT_PATH` | `~/.memex-backend/qdrant` | Embedded storage path |
| `MEMEX_QDRANT_URL` | `http://localhost:6333` | Server URL |
| `MEMEX_COLLECTION` | `memex` | Qdrant collection name |
| `MEMEX_CHUNK_TOKENS` | `512` | Max tokens per chunk |
| `MEMEX_CHUNK_OVERLAP` | `64` | Overlap between chunks |

## Data model

Each Qdrant point holds one chunk:

- **Vector:** embedding (1024 dimensions for the 0.6B model), cosine distance
- **Payload:** `path`, `heading`, `chunk_index`, `text`, `doc_hash`

## Chunking

Markdown is split on headings first so each chunk stays on one topic. Sections longer than `MEMEX_CHUNK_TOKENS` are split further with overlap. Plain `.txt` files are split by paragraph, then by size.

## Project structure

```
Memex-backend/
├── memex_backend/
│   ├── main.py         # FastAPI app and routes
│   ├── auth.py         # bearer token check
│   ├── config.py       # settings
│   ├── chunker.py      # markdown/text splitting
│   ├── embedder.py     # Qwen3-Embedding wrapper
│   ├── store.py        # Qdrant wrapper
│   └── schemas.py      # Pydantic models
├── tests/
├── pyproject.toml
└── README.md
```

## Testing

```bash
pytest
```

Tests use a fake embedder and in-memory Qdrant so they run without downloading model weights.

## Roadmap

- [ ] Reranker stage (Qwen3-Reranker)
- [ ] Hybrid search (dense + keyword)
- [ ] MCP server interface
- [ ] PDF and code repo ingestion
- [ ] Per-source collections and multi-user tokens

## Privacy

Embeddings are computed locally and vectors live in your own Qdrant instance. Nothing is sent to external services after the model weights are downloaded.

## License

MIT