"""Citation validation and verification for grounded RAG generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.entities.answer import RetrievedCandidate
from src.shared.logging import get_logger

logger = get_logger(__name__)

CITATION_REGEX = re.compile(r"\[(\d+)\]")

ABSTENTION_UNVERIFIED = (
    "I cannot answer this question based on the provided documents. "
    "The generated response referenced unverified sources."
)


@dataclass(frozen=True)
class CitationValidationResult:
    """Outcome of citation verification against retrieved candidates."""

    is_valid: bool
    cleaned_text: str
    valid_citations: list[int] = field(default_factory=list)
    orphaned_citations: list[int] = field(default_factory=list)
    triggered_abstention: bool = False


class CitationValidator:
    """
    Validates citation markers in LLM generated text against retrieved candidates.

    Rules:
    - Every citation [N] must map to candidate index 1 <= N <= len(candidates).
    - Orphaned / out-of-range citations are logged and stripped from generated text.
    - If all citations in the text are orphaned, or if no valid citations exist when citations
      were expected, the validator triggers an abstention to avoid hallucinated attribution.
    """

    def validate(
        self,
        generated_text: str,
        candidates: list[RetrievedCandidate],
        abstain_on_all_orphaned: bool = True,
    ) -> CitationValidationResult:
        """Validate bracketed citations in text against available candidates."""
        candidate_count = len(candidates)
        matches = [int(match) for match in CITATION_REGEX.findall(generated_text)]

        if not matches:
            # No citations found in text - answer stands as is
            return CitationValidationResult(
                is_valid=True,
                cleaned_text=generated_text.strip(),
                valid_citations=[],
                orphaned_citations=[],
                triggered_abstention=False,
            )

        valid_citations: list[int] = []
        orphaned_citations: list[int] = []

        for citation_num in matches:
            if 1 <= citation_num <= candidate_count:
                valid_citations.append(citation_num)
            else:
                orphaned_citations.append(citation_num)
                logger.warning(
                    f"Orphaned citation [{citation_num}] detected "
                    f"(available candidate count: {candidate_count})"
                )

        # Remove orphaned citation tokens from cleaned text
        def _strip_orphans(match: re.Match[str]) -> str:
            val = int(match.group(1))
            return "" if val in orphaned_citations else match.group(0)

        cleaned_text = CITATION_REGEX.sub(_strip_orphans, generated_text).strip()

        # Check if all citations were orphaned
        triggered_abstention = False
        if orphaned_citations and not valid_citations and abstain_on_all_orphaned:
            triggered_abstention = True
            cleaned_text = ABSTENTION_UNVERIFIED
            logger.warning("All citations were orphaned; triggering abstention.")

        return CitationValidationResult(
            is_valid=not triggered_abstention,
            cleaned_text=cleaned_text,
            valid_citations=sorted(set(valid_citations)),
            orphaned_citations=sorted(set(orphaned_citations)),
            triggered_abstention=triggered_abstention,
        )
