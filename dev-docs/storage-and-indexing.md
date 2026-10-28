# Storage and Indexing Model

## Qdrant collection

Document points each represent one chunk. Memory points each represent one complete memory with a single embedding. Both use the same cosine-distance collection and configured embedding dimension.

| Payload field | Purpose |
|---|---|
| `path` | Client-provided document identity and source path. |
| `heading` | Markdown heading chain for this chunk, or `null`. |
| `chunk_index` | Zero-based order within the document. |
| `text` | Chunk text returned to search clients. |
| `doc_hash` | Client-provided document version hash. |
| `document_content` | Original document body, retained to support reindexing. |

Point IDs are deterministic UUIDv5 values derived from the path and chunk index. Replacing a document deletes the existing points for that path before upserting its new points.

Memory point IDs are stable UUIDs. Their payload has `kind: memory`, `memory_id`, `text`, `created_at`, and `updated_at`. Document queries exclude memory points, and memory queries filter to them. Reindex snapshots both record types and re-embeds them after rebuilding the collection.

The original document content is currently repeated in every point payload for that document. This keeps reindexing possible using Qdrant alone, at the cost of increased storage proportional to the number of chunks. A future storage optimization could move source bodies to a separate document store, but would need to preserve reindex behavior.

## Chunking behavior

For paths that do not end in `.txt`, the chunker treats content as Markdown:

- A line matching a Markdown heading starts a new section.
- Nested heading context is retained as a `Parent > Child` heading chain.
- Text before the first heading is retained with a `null` heading.
- Long sections are split into windows with configured overlap.

For `.txt` paths, blank-line-separated paragraphs are independently chunked and headings are `null`.

Chunk sizing currently counts whitespace-delimited units, not the embedding model's tokenizer. The setting names use “tokens” for API/config compatibility, but actual chunk sizes can differ from model-token counts, especially for code, punctuation, and non-English text. Chunk text is normalized to single spaces only when a long section is split; sections under the configured limit retain their trimmed original text.

Empty or whitespace-only content yields no chunks. Since the store represents documents through chunk points, a zero-chunk document does not appear in source listings or counts.

## Reindex behavior and operational implications

The store snapshots unique paths, hashes, and original content from point payloads. It deletes and recreates the entire configured collection at the current model dimension, then rebuilds chunks and vectors for each snapshot document.

Reindex is synchronous and collection-wide. Do not run it concurrently with indexing, deletion, or search traffic that must remain uninterrupted. The current implementation does not stage a second collection or roll back automatically if an embedding error occurs after collection deletion. Back up Qdrant data before high-impact reindex operations.

If changing models changes the vector dimension, existing points remain in the old dimension until reindex is run. The active API reports the configured model dimension; callers should perform reindex before relying on search after a model change.
