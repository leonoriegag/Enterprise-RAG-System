"""PDF document parser using pypdf."""

import io

from pypdf import PdfReader

from src.domain.exceptions import IngestionError
from src.domain.interfaces.parsers import ParsedDocument, ParsedSection


class PDFParser:
    """Extracts text and page numbers from PDF files."""

    SUPPORTED_MIME_TYPES = {"application/pdf"}

    def can_parse(self, mime_type: str) -> bool:
        return mime_type.lower().split(";")[0].strip() in self.SUPPORTED_MIME_TYPES

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            stream = io.BytesIO(content)
            reader = PdfReader(stream)
            num_pages = len(reader.pages)
        except Exception as err:
            raise IngestionError(f"Failed to read PDF file '{filename}': {err}") from err

        sections: list[ParsedSection] = []
        full_text_parts: list[str] = []
        current_offset = 0

        for page_idx, page in enumerate(reader.pages):
            page_number = page_idx + 1
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            page_text_clean = page_text.strip()
            if page_text_clean:
                length = len(page_text_clean)
                sections.append(
                    ParsedSection(
                        content=page_text_clean,
                        page_number=page_number,
                        section_header=f"Page {page_number}",
                        character_start=current_offset,
                        character_end=current_offset + length,
                    )
                )
                full_text_parts.append(page_text_clean)
                current_offset += length + 2  # Account for double newline separator

        full_text = "\n\n".join(full_text_parts)

        return ParsedDocument(
            filename=filename,
            mime_type="application/pdf",
            full_text=full_text,
            sections=sections,
            metadata={
                "parser": "PDFParser",
                "page_count": num_pages,
                "extracted_pages": len(sections),
            },
        )
