# ADR 0001: PostgreSQL and pgvector for Unified Vector and Relational Storage

## Status
Accepted

## Context
Enterprise RAG architectures require persistent storage for structured business entities (tenants, users, roles, documents, access permissions, audit logs) as well as vector embeddings for semantic chunk retrieval.

Many modern architectures introduce standalone specialized vector databases (e.g., Pinecone, Milvus, Qdrant, Chroma, Weaviate) alongside a traditional relational database (PostgreSQL, MySQL). While specialized vector databases offer high-throughput approximate nearest neighbor (ANN) indexes, adopting a separate vector store introduces significant operational complexity:
1. **Dual-write consistency and drift**: Keeping access control lists (ACLs), document states, and embeddings synchronized across two independent data stores requires distributed transactions or asynchronous reconciliation workers.
2. **Authorization decoupling**: Document-level authorization and tenant isolation must either be replicated inside vector metadata or resolved through multi-stage network hops (fetching candidates from vector DB, then querying relational DB for permissions), creating security vulnerabilities and latency bottlenecks.
3. **Operational overhead**: Managing backups, point-in-time recovery, encryption at rest, connection pools, and monitoring for multiple database systems complicates deployment, especially in regulated enterprise environments and local development.

## Decision
We select **PostgreSQL 16+ with the `pgvector` extension** as the single unified persistence engine for both relational domain data and vector embeddings.

Specifically:
- Embeddings are stored as `vector(dim)` columns directly on the `document_chunks` table.
- Approximate Nearest Neighbor (ANN) search is accelerated using **HNSW (Hierarchical Navigable Small World)** indexes (`vector_cosine_ops`), which provide low query latency and high recall without requiring index rebuilds during incremental document ingestion.
- PostgreSQL Row-Level Security (RLS) is applied at the engine level, guaranteeing that vector similarity queries (`<=>` cosine distance) are evaluated exclusively against chunks belonging to the authenticated tenant.
- Lexical full-text search vectors (`tsvector`) are stored in the same table, allowing unified hybrid query execution within a single database transaction.

## Consequences

### Positive
- **Guaranteed Consistency**: Document deletions, permission updates, and chunk embeddings are committed or rolled back in a single ACID transaction. No orphaned vectors.
- **Unified Security Model**: PostgreSQL Row-Level Security and indexed relational joins filter candidates at the database engine level before semantic scoring.
- **Simplified Operational Footprint**: A single Docker container or managed RDS/Cloud SQL PostgreSQL instance serves all persistence needs, drastically reducing operational complexity and cost.
- **Provider Portability**: Standard SQL and standard extension supported across AWS RDS, Azure Database, Google Cloud SQL, and self-hosted Docker containers.

### Negative / Trade-offs
- Very large scale deployments (100M+ vectors) may require horizontal sharding or dedicated vector clusters. For the target enterprise scale (up to 10M chunks per cluster), PostgreSQL HNSW provides sub-20ms retrieval latencies, making this trade-off fully acceptable.
- Requires PostgreSQL instances to have the `pgvector` extension compiled/enabled. This is handled via standard Docker images (`pgvector/pgvector:pg16`).
