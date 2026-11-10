"""Unit tests for the structure-preserving recursive token chunker."""

from src.domain.interfaces.parsers import ParsedDocument, ParsedSection
from src.domain.services.chunker import RecursiveTokenChunker


def test_chunker_handles_short_document() -> None:
    chunker = RecursiveTokenChunker(default_chunk_size=100, default_overlap=20)
    section = ParsedSection(
        content="Short ACME policy statement that easily fits within one single chunk.",
        page_number=1,
        section_header="Introduction",
    )
    doc = ParsedDocument(
        filename="intro.txt",
        mime_type="text/plain",
        full_text=section.content,
        sections=[section],
    )

    chunks = chunker.chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].section_header == "Introduction"
    assert "Short ACME policy" in chunks[0].content


def test_chunker_splits_long_document_with_overlap() -> None:
    # 50 tokens ~ 200 chars
    chunker = RecursiveTokenChunker(default_chunk_size=50, default_overlap=15)

    long_paragraph = (
        "Paragraph 1 discusses the fundamental enterprise architecture of ACME. "
        "It outlines the necessity for high-availability database replication. "
        "Furthermore, it emphasizes tenant isolation across all shared persistence models.\n\n"
        "Paragraph 2 dives deeper into the authorization policy matrix. "
        "Every document is classified into Public, Internal, Confidential, or Restricted tiers. "
        "Row-level security ensures no leakage happens even if queries are malformed.\n\n"
        "Paragraph 3 covers hybrid retrieval strategies using reciprocal rank fusion."
    )

    section = ParsedSection(
        content=long_paragraph,
        page_number=4,
        section_header="Section 2.1 Architecture",
    )
    doc = ParsedDocument(
        filename="arch.txt",
        mime_type="text/plain",
        full_text=long_paragraph,
        sections=[section],
    )

    chunks = chunker.chunk(doc)
    assert len(chunks) > 1

    # Verify all chunks inherit provenance
    for chunk in chunks:
        assert chunk.page_number == 4
        assert chunk.section_header == "Section 2.1 Architecture"
        assert chunk.token_count > 0

    # Verify sequential indexing
    for idx, chunk in enumerate(chunks):
        assert chunk.chunk_index == idx


def test_chunker_preserves_multiple_sections() -> None:
    chunker = RecursiveTokenChunker(default_chunk_size=200, default_overlap=20)
    sec1 = ParsedSection(content="Section One Content", page_number=1, section_header="Part 1")
    sec2 = ParsedSection(content="Section Two Content", page_number=2, section_header="Part 2")
    doc = ParsedDocument(
        filename="multi.md",
        mime_type="text/markdown",
        full_text="Section One Content\nSection Two Content",
        sections=[sec1, sec2],
    )

    chunks = chunker.chunk(doc)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[0].section_header == "Part 1"
    assert chunks[1].page_number == 2
    assert chunks[1].section_header == "Part 2"
