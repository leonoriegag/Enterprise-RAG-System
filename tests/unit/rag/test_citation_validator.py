"""Unit tests for citation validation and orphan handling."""

from uuid import uuid4

from src.application.rag.citation_validator import ABSTENTION_UNVERIFIED, CitationValidator
from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department


def make_candidate(content: str = "Test chunk content.") -> RetrievedCandidate:
    chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=uuid4(),
        chunk_index=0,
        content=content,
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,
    )
    return RetrievedCandidate(
        chunk=chunk,
        document_title="IT Policy",
        semantic_score=0.85,
        lexical_score=0.75,
        rrf_score=0.03,
    )


def test_valid_citations_are_accepted() -> None:
    validator = CitationValidator()
    candidates = [make_candidate(), make_candidate()]
    text = "Employees must use password managers [1] and enable MFA [2]."

    result = validator.validate(text, candidates)

    assert result.is_valid is True
    assert result.triggered_abstention is False
    assert result.valid_citations == [1, 2]
    assert result.orphaned_citations == []
    assert result.cleaned_text == text


def test_orphaned_citations_are_stripped_from_text() -> None:
    validator = CitationValidator()
    candidates = [make_candidate()]  # Only 1 candidate available
    text = "Data is encrypted at rest [1] and backed up offsite [4]."

    result = validator.validate(text, candidates)

    assert result.is_valid is True
    assert result.valid_citations == [1]
    assert result.orphaned_citations == [4]
    assert "[4]" not in result.cleaned_text
    assert "[1]" in result.cleaned_text


def test_all_orphaned_citations_trigger_abstention() -> None:
    validator = CitationValidator()
    candidates = [make_candidate()]
    text = "Unverified statement from non-existent document [99]."

    result = validator.validate(text, candidates)

    assert result.is_valid is False
    assert result.triggered_abstention is True
    assert result.cleaned_text == ABSTENTION_UNVERIFIED
    assert result.orphaned_citations == [99]
    assert result.valid_citations == []


def test_text_without_citations_is_valid() -> None:
    validator = CitationValidator()
    candidates = [make_candidate()]
    text = "General guidance note without explicit citations."

    result = validator.validate(text, candidates)

    assert result.is_valid is True
    assert result.triggered_abstention is False
    assert result.cleaned_text == text
    assert result.valid_citations == []
    assert result.orphaned_citations == []


def test_empty_candidates_with_citations_in_text_triggers_abstention() -> None:
    validator = CitationValidator()
    result = validator.validate("Response citing [1].", [])

    assert result.triggered_abstention is True
    assert result.is_valid is False
    assert 1 in result.orphaned_citations
