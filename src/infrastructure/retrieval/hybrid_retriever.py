"""PostgreSQL hybrid retriever combining semantic (pgvector) and lexical (FTS) search with RRF."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.retrieval import RetrievalFilter
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole
from src.shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class RetrievalExecutionStats:
    """Execution timing and count diagnostics for a hybrid retrieval operation."""

    query: str
    semantic_count: int
    lexical_count: int
    fused_count: int
    execution_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class PostgresHybridRetriever:
    """PostgreSQL hybrid retriever implementing pgvector vector search, FTS, and RRF fusion."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self.session = session
        self.embedding_provider = embedding_provider
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilter,
        top_k: int = 5,
    ) -> list[RetrievedCandidate]:
        """Execute hybrid search applying pre-retrieval authorization and RRF fusion."""
        candidates, _stats = await self.retrieve_with_stats(query, filters, top_k=top_k)
        return candidates

    async def retrieve_with_stats(
        self,
        query: str,
        filters: RetrievalFilter,
        top_k: int = 5,
    ) -> tuple[list[RetrievedCandidate], RetrievalExecutionStats]:
        """Execute hybrid search and return candidates along with performance diagnostics."""
        start_time = time.monotonic()

        # 1. Generate query embedding
        query_embeddings = await self.embedding_provider.embed_documents([query])
        query_vector = query_embeddings[0]

        # 2. Build pre-retrieval security and authorization where-clause
        where_conditions = [
            "c.tenant_id = :tenant_id",
            "c.access_level <= :max_clearance",
        ]
        params: dict[str, Any] = {
            "tenant_id": str(filters.tenant_id),
            "max_clearance": filters.max_clearance.value,
            "top_k_candidates": top_k * 3,  # Candidate pool for fusion
            "query_text": query,
            "query_vector": str(query_vector),
        }

        # Department boundary enforcement
        if filters.target_department is not None:
            where_conditions.append("c.department = :target_dept")
            params["target_dept"] = filters.target_department.value
        elif filters.role != UserRole.ADMIN:
            where_conditions.append("c.department IN (:user_dept, :general_dept)")
            params["user_dept"] = filters.department.value
            params["general_dept"] = Department.GENERAL.value

        base_where = " AND ".join(where_conditions)

        # 3. Dense semantic query via pgvector cosine distance
        semantic_query = text(f"""
            SELECT
                c.id AS chunk_id,
                c.document_id,
                c.tenant_id,
                c.chunk_index,
                c.content,
                c.department,
                c.access_level,
                c.page_number,
                c.section_header,
                c.token_count,
                c.character_start,
                c.character_end,
                d.title AS document_title,
                (c.embedding <=> CAST(:query_vector AS vector)) AS distance,
                ROW_NUMBER() OVER (
                    ORDER BY c.embedding <=> CAST(:query_vector AS vector) ASC
                ) AS semantic_rank
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE {base_where}
            ORDER BY distance ASC
            LIMIT :top_k_candidates
        """)

        # 4. Sparse lexical query via PostgreSQL Full-Text Search
        lexical_query = text(f"""
            SELECT
                c.id AS chunk_id,
                c.document_id,
                c.tenant_id,
                c.chunk_index,
                c.content,
                c.department,
                c.access_level,
                c.page_number,
                c.section_header,
                c.token_count,
                c.character_start,
                c.character_end,
                d.title AS document_title,
                ts_rank_cd(c.fts_vector, plainto_tsquery('english', :query_text)) AS lexical_score,
                ROW_NUMBER() OVER (
                    ORDER BY ts_rank_cd(
                        c.fts_vector, plainto_tsquery('english', :query_text)
                    ) DESC
                ) AS lexical_rank
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE {base_where}
              AND c.fts_vector @@ plainto_tsquery('english', :query_text)
            ORDER BY lexical_score DESC
            LIMIT :top_k_candidates
        """)

        sem_result = await self.session.execute(semantic_query, params)
        sem_rows = sem_result.mappings().all()

        lex_result = await self.session.execute(lexical_query, params)
        lex_rows = lex_result.mappings().all()

        # 5. Reciprocal Rank Fusion (RRF)
        # RRF score = 1 / (k + rank)
        rrf_scores: dict[str, float] = {}
        semantic_scores: dict[str, float] = {}
        lexical_scores: dict[str, float] = {}
        row_map: dict[str, Any] = {}

        for row in sem_rows:
            cid = str(row["chunk_id"])
            rank = int(row["semantic_rank"])
            sem_score = 1.0 - float(row["distance"])
            semantic_scores[cid] = sem_score
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))
            row_map[cid] = row

        for row in lex_rows:
            cid = str(row["chunk_id"])
            rank = int(row["lexical_rank"])
            lex_score = float(row["lexical_score"])
            lexical_scores[cid] = lex_score
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))
            if cid not in row_map:
                row_map[cid] = row

        # Sort candidates by combined RRF score descending
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[
            :top_k
        ]

        candidates: list[RetrievedCandidate] = []
        for cid in sorted_chunk_ids:
            row = row_map[cid]
            chunk_entity = DocumentChunk(
                id=UUID(str(row["chunk_id"])),
                document_id=UUID(str(row["document_id"])),
                tenant_id=UUID(str(row["tenant_id"])),
                chunk_index=int(row["chunk_index"]),
                content=str(row["content"]),
                department=Department(str(row["department"])),
                access_level=AccessLevel(int(row["access_level"])),
                page_number=int(row["page_number"]) if row["page_number"] is not None else None,
                section_header=(
                    str(row["section_header"]) if row["section_header"] is not None else None
                ),
                token_count=int(row["token_count"]),
                character_start=int(row["character_start"]),
                character_end=int(row["character_end"]),
            )

            candidate = RetrievedCandidate(
                chunk=chunk_entity,
                document_title=str(row["document_title"]),
                semantic_score=semantic_scores.get(cid, 0.0),
                lexical_score=lexical_scores.get(cid, 0.0),
                rrf_score=rrf_scores.get(cid, 0.0),
            )
            candidates.append(candidate)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        stats = RetrievalExecutionStats(
            query=query,
            semantic_count=len(sem_rows),
            lexical_count=len(lex_rows),
            fused_count=len(candidates),
            execution_time_ms=elapsed_ms,
        )

        logger.debug(
            f"Hybrid retrieval finished in {elapsed_ms:.2f}ms: "
            f"semantic={len(sem_rows)}, lexical={len(lex_rows)}, fused={len(candidates)}"
        )
        return candidates, stats


class PassThroughReranker:
    """Default pass-through reranker that preserves RRF ordering."""

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedCandidate],
        top_n: int = 3,
    ) -> list[RetrievedCandidate]:
        """Return top_n candidates preserving hybrid retrieval order."""
        return candidates[:top_n]
