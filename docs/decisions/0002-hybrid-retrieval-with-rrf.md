# ADR 0002: Hybrid Retrieval Engine with Reciprocal Rank Fusion (RRF)

## Status
Accepted

## Context
Standard enterprise knowledge bases contain a diverse spectrum of queries and documents:
- **Conceptual and semantic queries**: e.g., *"What is our policy regarding remote work during severe weather?"* — where semantic embedding search excels by understanding intent and synonyms even if literal words do not match.
- **Specific lexical queries**: e.g., error codes (`ERR-403-TOKEN-EXPIRED`), exact policy numbers (`SEC-POL-042`), employee titles, acronyms (`HIPAA`, `SSO`, `CIDR`), or specific function names — where dense vector models frequently suffer from "semantic drift" or fail to prioritize exact token matches.

Solely relying on vector embeddings leads to poor precision on exact-match lookups. Solely relying on keyword search (BM25 / Full-Text Search) fails to capture semantic synonyms and natural language phrasing.

Combining lexical and dense semantic search requires a robust ranking fusion strategy. Standard linear score combination:
$$Score(d) = \alpha \cdot S_{semantic}(d) + (1 - \alpha) \cdot S_{lexical}(d)$$
suffers from score calibration issues: cosine similarities and BM25 / ts_rank scores live on fundamentally different non-linear scales and distributions, making static weight tuning brittle across varying document sets.

## Decision
We implement a **Hybrid Retrieval Engine** combining:
1. **Dense Semantic Search**: pgvector cosine distance (`1 - (embedding <=> query_vector)`).
2. **Lexical Full-Text Search**: PostgreSQL `tsvector` with `ts_rank_cd` (Cover Density ranking with English stemming).
3. **Rank Fusion**: **Reciprocal Rank Fusion (RRF)** as the default deterministic fusion algorithm:
   $$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
   where:
   - $M$ is the set of retrieval channels ($M = \{\text{semantic}, \text{lexical}\}$).
   - $r_m(d)$ is the 1-based rank of document chunk $d$ in channel $m$.
   - $k$ is a smoothing constant, set to $k = 60$ (the empirically validated standard in IR literature).
4. **Pluggable Cross-Encoder Reranking Interface**: An optional post-fusion cross-encoder reranker stage (`Reranker` interface) that rescores the top-N fused candidates when enabled, while falling back gracefully to pure RRF when disabled or offline.

## Consequences

### Positive
- **Scale-Invariant Fusion**: RRF relies exclusively on relative rank positions rather than arbitrary raw score scales, eliminating brittle weight-tuning parameters across domains.
- **Robust Out-of-the-Box Quality**: Guarantees high recall for both conceptual queries and exact identifier lookups.
- **Single-Database Efficiency**: Both semantic vector search and full-text search run inside PostgreSQL in a single unified query or concurrent subqueries, minimizing network roundtrips.
- **Offline & Online Compatibility**: Works completely offline without external APIs; can be optionally enhanced with neural rerankers (e.g., Cohere, BGE-reranker) when credentials are provided.

### Negative / Trade-offs
- Computing both vector distance and full-text rank adds slight computational overhead compared to single-channel retrieval (typically 5–15ms additional database latency), which is negligible relative to LLM generation time (500–2000ms).
