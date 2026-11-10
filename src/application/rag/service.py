"""RAG application service coordinating retrieval, reranking, generation, and validation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.application.auth.context import AuthContext
from src.application.rag.citation_validator import CitationValidator
from src.application.rag.prompt_builder import PromptBuilder
from src.domain.entities.answer import GroundedAnswer
from src.domain.entities.citation import Citation
from src.domain.interfaces.llm import LLMProvider
from src.domain.interfaces.retrieval import HybridRetriever, Reranker, RetrievalFilter
from src.domain.services.normalizer import TextNormalizer
from src.domain.value_objects.department import Department
from src.shared.logging import get_logger

logger = get_logger(__name__)

ABSTENTION_INSUFFICIENT_EVIDENCE = (
    "I cannot answer this question based on the provided documents. "
    "No sufficiently relevant content was found in the knowledge base."
)


@dataclass(frozen=True)
class RAGResult:
    """Outcome of a RAG query answering execution."""

    answer: GroundedAnswer
    candidates_retrieved: int
    candidates_used: int
    execution_time_ms: float
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def answer_text(self) -> str:
        """Convenience property for answer content."""
        return self.answer.content

    @property
    def citations(self) -> list[Citation]:
        """Convenience property for citation list."""
        return self.answer.citations

    @property
    def did_abstain(self) -> bool:
        """Convenience property for abstention status."""
        return self.answer.abstained


class RAGService:
    """
    Core RAG question-answering orchestrator.

    Pipeline:
    1. Query normalization
    2. Context resolution and pre-retrieval access control filtering
    3. Hybrid retrieval (pgvector + FTS + RRF)
    4. Optional reranking
    5. Evidence threshold and abstention check
    6. Defensive prompt synthesis
    7. LLM generation
    8. Citation validation and structure linking
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        llm_provider: LLMProvider,
        reranker: Reranker | None = None,
        prompt_builder: PromptBuilder | None = None,
        citation_validator: CitationValidator | None = None,
        normalizer: TextNormalizer | None = None,
        min_evidence_candidates: int = 1,
        default_top_k: int = 5,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.reranker = reranker
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.citation_validator = citation_validator or CitationValidator()
        self.normalizer = normalizer or TextNormalizer()
        self.min_evidence_candidates = min_evidence_candidates
        self.default_top_k = default_top_k

    async def ask(
        self,
        query: str,
        auth_context: AuthContext,
        target_department: Department | None = None,
        top_k: int | None = None,
        confidence_threshold: float = 0.0,
    ) -> RAGResult:
        """Answer a query strictly grounded in authorized enterprise knowledge."""
        start_time = time.monotonic()
        k = top_k or self.default_top_k

        # 1. Query normalization
        normalized_query = self.normalizer.normalize(query)

        # 2. Pre-retrieval access authorization filters
        filters = RetrievalFilter(
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            role=auth_context.role,
            department=auth_context.department,
            max_clearance=auth_context.max_clearance,
            target_department=target_department,
        )

        # 3. Hybrid candidate retrieval
        candidates = await self.retriever.retrieve(
            query=normalized_query,
            filters=filters,
            top_k=k,
        )
        candidates_retrieved = len(candidates)

        # 4. Optional confidence threshold filtering
        if confidence_threshold > 0.0:
            candidates = [c for c in candidates if c.final_score >= confidence_threshold]

        # 5. Optional reranking
        if self.reranker is not None and candidates:
            candidates = await self.reranker.rerank(
                query=normalized_query,
                candidates=candidates,
                top_n=k,
            )

        # 6. Evidence sufficiency check -> Abstention if insufficient
        if len(candidates) < self.min_evidence_candidates:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            grounded_answer = GroundedAnswer(
                query=query,
                content=ABSTENTION_INSUFFICIENT_EVIDENCE,
                citations=[],
                abstained=True,
                confidence_score=0.0,
                execution_metadata={"reason": "insufficient_evidence"},
            )
            return RAGResult(
                answer=grounded_answer,
                candidates_retrieved=candidates_retrieved,
                candidates_used=0,
                execution_time_ms=elapsed_ms,
                model_name=self.llm_provider.model_name,
                prompt_tokens=0,
                completion_tokens=len(ABSTENTION_INSUFFICIENT_EVIDENCE.split()),
                metadata={"reason": "insufficient_evidence"},
            )

        # 7. Defensive prompt construction
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(
            query=normalized_query,
            candidates=candidates,
        )

        # 8. Generation via LLM provider
        generation = await self.llm_provider.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 9. Citation verification
        val_result = self.citation_validator.validate(
            generated_text=generation.content,
            candidates=candidates,
        )

        # 10. Construct structured Citation entities
        citations: list[Citation] = []
        for c_idx in val_result.valid_citations:
            candidate = candidates[c_idx - 1]
            citation = Citation(
                document_id=candidate.chunk.document_id,
                chunk_id=candidate.chunk.id,
                citation_index=c_idx,
                document_title=candidate.document_title,
                page_number=candidate.chunk.page_number,
                section_header=candidate.chunk.section_header,
                snippet=candidate.chunk.content[:250],
            )
            citations.append(citation)

        did_abstain = generation.did_abstain or val_result.triggered_abstention
        max_score = max((c.final_score for c in candidates), default=0.0)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        grounded_answer = GroundedAnswer(
            query=query,
            content=val_result.cleaned_text,
            citations=citations,
            abstained=did_abstain,
            confidence_score=max_score,
            execution_metadata={
                "model": generation.model_name,
                "finish_reason": generation.finish_reason,
                "orphaned_citations": val_result.orphaned_citations,
            },
        )

        return RAGResult(
            answer=grounded_answer,
            candidates_retrieved=candidates_retrieved,
            candidates_used=len(candidates),
            execution_time_ms=elapsed_ms,
            model_name=generation.model_name,
            prompt_tokens=generation.prompt_tokens,
            completion_tokens=generation.completion_tokens,
            metadata={
                "orphaned_citations": val_result.orphaned_citations,
                "valid_citations_count": len(citations),
            },
        )
