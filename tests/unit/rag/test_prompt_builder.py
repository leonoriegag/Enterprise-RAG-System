"""Unit tests for defensive prompt construction."""

from uuid import uuid4

from src.application.rag.prompt_builder import PromptBuilder
from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department


def make_candidate(
    content: str,
    title: str = "Employee Handbook",
    section: str | None = None,
    page: int | None = None,
) -> RetrievedCandidate:
    chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=uuid4(),
        chunk_index=0,
        content=content,
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
        section_header=section,
        page_number=page,
    )
    return RetrievedCandidate(
        chunk=chunk,
        document_title=title,
        rrf_score=0.032,
    )


def test_system_prompt_enforces_grounding_and_untrusted_notice() -> None:
    builder = PromptBuilder()
    sys_prompt = builder.build_system_prompt()

    assert "CRITICAL SECURITY AND GROUNDING RULES" in sys_prompt
    assert "UNTRUSTED" in sys_prompt
    assert "Ignore previous instructions" in sys_prompt
    assert "retrieved_context" in sys_prompt


def test_user_prompt_formats_sources_and_question() -> None:
    builder = PromptBuilder()
    candidates = [
        make_candidate("Employees get 20 days annual leave.", section="Paid Time Off", page=12),
        make_candidate("Sick leave requires a medical certificate.", page=14),
    ]

    prompt = builder.build_user_prompt("How many vacation days do employees get?", candidates)

    assert "<retrieved_context>" in prompt
    assert "</retrieved_context>" in prompt
    assert "<source 1>" in prompt
    assert "Document: Employee Handbook" in prompt
    assert "Section: Paid Time Off" in prompt
    assert "Page: 12" in prompt
    assert "Employees get 20 days annual leave." in prompt
    assert "<source 2>" in prompt
    assert "Page: 14" in prompt
    assert "<user_question>" in prompt
    assert "How many vacation days do employees get?" in prompt


def test_user_prompt_handles_empty_candidates() -> None:
    builder = PromptBuilder()
    prompt = builder.build_user_prompt("What is the wifi password?", [])

    assert "<retrieved_context>" in prompt
    assert "<user_question>\nWhat is the wifi password?\n</user_question>" in prompt


def test_extract_context_blocks() -> None:
    builder = PromptBuilder()
    c1 = make_candidate("First chunk.")
    c2 = make_candidate("Second chunk.")

    blocks = builder.extract_context_blocks([c1, c2])
    assert blocks == ["First chunk.", "Second chunk."]
