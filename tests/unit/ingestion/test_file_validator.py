"""Unit tests for document file validation."""

import pytest

from src.domain.exceptions import IngestionError
from src.domain.services.validator import DocumentValidator


def test_validator_rejects_empty_file() -> None:
    validator = DocumentValidator(max_size_mb=25)
    with pytest.raises(IngestionError, match="empty"):
        validator.validate(b"", "empty.txt", "text/plain")


def test_validator_rejects_oversized_file() -> None:
    validator = DocumentValidator(max_size_mb=1)  # 1 MB limit
    oversized_bytes = b"a" * (2 * 1024 * 1024)  # 2 MB
    with pytest.raises(IngestionError, match="exceeds maximum allowed"):
        validator.validate(oversized_bytes, "big.txt", "text/plain")


def test_validator_validates_text_and_markdown() -> None:
    validator = DocumentValidator()
    txt_res = validator.validate(b"Hello ACME", "notes.txt", "text/plain")
    assert txt_res.is_valid is True
    assert txt_res.detected_format == "txt"

    md_res = validator.validate(b"# Policy\nContent", "policy.md", "text/markdown")
    assert md_res.is_valid is True
    assert md_res.detected_format == "md"


def test_validator_verifies_pdf_magic_bytes() -> None:
    validator = DocumentValidator()
    valid_pdf = b"%PDF-1.7\nstream\n..."
    res = validator.validate(valid_pdf, "doc.pdf", "application/pdf")
    assert res.is_valid is True
    assert res.detected_format == "pdf"

    invalid_pdf = b"NOT_A_REAL_PDF"
    with pytest.raises(IngestionError, match="lacks magic signature"):
        validator.validate(invalid_pdf, "spoofed.pdf", "application/pdf")


def test_validator_verifies_docx_magic_bytes() -> None:
    validator = DocumentValidator()
    valid_docx = b"PK\x03\x04\x14\x00\x06\x00..."
    res = validator.validate(
        valid_docx,
        "doc.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert res.is_valid is True
    assert res.detected_format == "docx"

    invalid_docx = b"PK_FAKE_ZIP"
    with pytest.raises(IngestionError, match="lacks magic signature"):
        validator.validate(
            invalid_docx,
            "spoofed.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def test_validator_rejects_unsupported_extensions() -> None:
    validator = DocumentValidator()
    with pytest.raises(IngestionError, match="Unsupported format"):
        validator.validate(b"\x7fELF...", "malware.exe", "application/x-msdownload")
