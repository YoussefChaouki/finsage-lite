# ADR-002: pgvector Over ChromaDB or Pinecone

## Status
Accepted

## Context
The system needs a vector store for embedding-based retrieval.
Options considered: pgvector (PostgreSQL extension), ChromaDB
(embedded vector DB), Pinecone (managed cloud service).

## Decision
Use PostgreSQL with pgvector extension for all vector storage and
similarity search.

## Rationale
- **Single database**: Chunks, documents, and vectors live in the same
  PostgreSQL instance. No data synchronization between systems.
- **SQL-native filtering**: Pre-filtering by document_id, section, fiscal_year
  happens in the same query as vector search — no post-filtering needed
- **Infrastructure consistency**: Extends the existing CITADEL PostgreSQL setup.
  Same backup, monitoring, and migration tooling (Alembic)
- **No vendor lock-in**: pgvector is open-source, runs anywhere PostgreSQL runs
- **Cost**: Zero additional infrastructure cost vs managed services

## Consequences
### Positive
- Simplified deployment (one Docker container for DB + vectors)
- Transactional consistency between metadata and embeddings
- IVFFlat index provides sub-millisecond search at our corpus scale (~1k chunks)

### Negative
- At scale (>1M vectors), pgvector's IVFFlat requires careful tuning
  (lists parameter) and may underperform dedicated vector DBs
- No built-in hybrid search (BM25 handled separately in-memory)
- Missing features like automatic re-indexing on insert (manual REINDEX needed)

## Scaling Path
For >100k chunks: switch to HNSW index (pgvector 0.5+).
For >1M chunks: evaluate Qdrant or Weaviate with pgvector as metadata store.
