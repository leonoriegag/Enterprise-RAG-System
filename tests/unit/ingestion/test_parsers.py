"""Unit tests for document parsers."""

import io

import docx
import pytest
from pypdf import PdfWriter

from src.infrastructure.documents.parsers.docx_parser import DOCXParser
from src.infrastructure.documents.parsers.factory import ParserRegistry
from src.infrastructure.documents.parsers.markdown_parser import MarkdownParser
from src.infrastructure.documents.parsers.pdf_parser import PDFParser
from src.infrastructure.documents.parsers.text_parser import TextParser


@pytest.mark.asyncio
async def test_text_parser() -> None:
    parser = TextParser()
    assert parser.can_parse("text/plain") is True
    assert parser.can_parse("application/pdf") is False

    raw_bytes = b"ACME Enterprise Internal Operational Manual\nLine 2 content."
    parsed = await parser.parse(raw_bytes, "manual.txt")

    assert parsed.filename == "manual.txt"
    assert parsed.mime_type == "text/plain"
    assert "ACME Enterprise" in parsed.full_text
    assert len(parsed.sections) == 1


@pytest.mark.asyncio
async def test_markdown_parser_extracts_headings() -> None:
    parser = MarkdownParser()
    assert parser.can_parse("text/markdown") is True

    md_content = b"""# ACME Security Standard
Overview of IT security.

## Section 1: Password Complexity
Passwords must be 14 characters minimum.

### Section 1.1: Multi-Factor Authentication
MFA is required for all corporate systems.
"""
    parsed = await parser.parse(md_content, "security.md")

    assert parsed.mime_type == "text/markdown"
    assert len(parsed.sections) >= 3
    headers = [s.section_header for s in parsed.sections if s.section_header]
    assert any("H1: ACME Security Standard" in h for h in headers)
    assert any("H2: Section 1: Password Complexity" in h for h in headers)
    assert any("H3: Section 1.1: Multi-Factor Authentication" in h for h in headers)


@pytest.mark.asyncio
async def test_pdf_parser_extracts_pages() -> None:
    parser = PDFParser()
    assert parser.can_parse("application/pdf") is True

    # Generate an in-memory 2-page PDF
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    pdf_stream = io.BytesIO()
    writer.write(pdf_stream)
    pdf_bytes = pdf_stream.getvalue()

    parsed = await parser.parse(pdf_bytes, "test.pdf")
    assert parsed.mime_type == "application/pdf"
    assert parsed.metadata["page_count"] == 2


@pytest.mark.asyncio
async def test_docx_parser_extracts_paragraphs_and_headings() -> None:
    parser = DOCXParser()
    assert (
        parser.can_parse("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        is True
    )

    # Generate an in-memory DOCX with heading and paragraph
    doc = docx.Document()
    doc.add_heading("Expense Reimbursement Policy", level=1)
    doc.add_paragraph("Meals are reimbursed up to $75 per day.")
    docx_stream = io.BytesIO()
    doc.save(docx_stream)
    docx_bytes = docx_stream.getvalue()

    parsed = await parser.parse(docx_bytes, "policy.docx")
    assert "application/vnd.openxmlformats" in parsed.mime_type
    assert len(parsed.sections) >= 1
    assert any(s.section_header == "Expense Reimbursement Policy" for s in parsed.sections)
    assert "Meals are reimbursed" in parsed.full_text


def test_parser_registry_fallback() -> None:
    registry = ParserRegistry()
    pdf_parser = registry.get_parser("application/pdf")
    assert isinstance(pdf_parser, PDFParser)

    # Fallback via extension
    md_parser = registry.get_parser("unknown/type", filename="document.md")
    assert isinstance(md_parser, MarkdownParser)
