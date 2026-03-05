# Scaling Considerations

> This section documents how the current architecture would evolve
> to handle production-scale workloads. The current implementation
> is optimized for correctness and portfolio demonstration.

## Current Limitations and Scaling Paths

### Vector Search (pgvector)
**Current**: IVFFlat index with lists=100. Handles ~10k vectors with
sub-10ms P99 latency.

**At 100k vectors**: Switch to HNSW index (pgvector 0.5+). HNSW provides
better recall-latency tradeoffs at scale without manual list tuning.

**At 1M+ vectors**: Consider dedicated vector DB (Qdrant, Weaviate)
with pgvector retained as metadata/relational store. This separates
the vector search workload from transactional queries.

### BM25 Index
**Current**: In-memory rank_bm25 rebuilt at startup. Single-process.

**At 50k+ chunks**: Memory footprint becomes significant (~500MB).
Move to Redis-backed BM25 or Elasticsearch for shared indexing
across multiple API instances.

**Multi-instance deployment**: Current design requires each instance to
hold its own BM25 index. Solutions: shared Elasticsearch cluster,
or Redis-based index with pub/sub invalidation on new ingestions.

### Ingestion Pipeline
**Current**: Synchronous per-request. One filing at a time.

**At scale**: Decouple ingestion into a background task queue (Celery + Redis
or FastAPI BackgroundTasks). The API returns immediately with a job ID;
the client polls for completion. Enables batch ingestion of multiple
filings concurrently.

### Embedding Generation
**Current**: CPU-only sentence-transformers in the API process.

**At scale**: Move to a dedicated embedding service (GPU-backed) behind
a load balancer. Batch requests for throughput. Consider ONNX Runtime
for 2-3x inference speedup without GPU.

### API
**Current**: Single Uvicorn process with async handlers.

**At scale**: Multiple Uvicorn workers behind nginx/Traefik. Add
connection pooling (PgBouncer) between API instances and PostgreSQL.
Implement response caching (Redis) for repeated queries.

## What I Would Change First

If this system needed to handle 100 concurrent users:
1. Add Redis for BM25 index sharing + response caching
2. Switch pgvector index to HNSW
3. Add PgBouncer for connection pooling
4. Move ingestion to background tasks with progress tracking

Total estimated effort: ~2 weeks.
