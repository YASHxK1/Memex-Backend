# Memex Backend Developer Docs

This folder is the engineering guide for the self-hosted Memex semantic search service. It describes the backend implementation and how to run, extend, and troubleshoot it. The repository root [README](../README.md) remains the short install and product overview.

## Contents

- [Architecture and request flows](architecture.md)
- [HTTP API reference](api.md)
- [Configuration and operations](configuration-and-operations.md)
- [Storage and indexing model](storage-and-indexing.md)
- [Development and tests](development.md)

## Service at a glance

The service accepts Markdown or text documents, splits them into chunks, embeds chunks with Sentence Transformers, and stores vectors and payloads in Qdrant. Search embeds a query and returns the closest matching chunks. All `/v1/*` routes require a configured Bearer token; `/health` is public.

The supported first release is single-user and has one Qdrant collection. PDF/repository ingestion, keyword search, reranking, MCP, and per-user isolation are roadmap work, not current behavior.
