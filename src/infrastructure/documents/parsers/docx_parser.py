"""DOCX document parser using python-docx."""

import io

import docx

from src.domain.exceptions import IngestionError
from src.domain.interfaces.parsers import ParsedDocument, ParsedSection


class DOCXParser:
    """Extracts text and hierarchical headings from DOCX files."""

    SUPPORTED_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/docx",
    }

    def can_parse(self, mime_type: str) -> bool:
        return mime_type.lower().split(";")[0].strip() in self.SUPPORTED_MIME_TYPES

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            stream = io.BytesIO(content)
            doc = docx.Document(stream)
        except Exception as err:
            raise IngestionError(f"Failed to read DOCX file '{filename}': {err}") from err

        sections: list[ParsedSection] = []
        full_text_parts: list[str] = []

        current_header: str | None = None
        current_paragraphs: list[str] = []
        current_offset = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name.lower() if para.style and para.style.name else ""

            # Check if paragraph is a heading
            if "heading" in style_name or "title" in style_name:
                # Flush previous section
                if current_paragraphs:
                    sec_text = "\n".join(current_paragraphs)
                    length = len(sec_text)
                    sections.append(
                        ParsedSection(
                            content=sec_text,
                            section_header=current_header,
                            character_start=current_offset,
                            character_end=current_offset + length,
                        )
                    )
                    full_text_parts.append(sec_text)
                    current_offset += length + 2
                    current_paragraphs = []

                current_header = text
            else:
                current_paragraphs.append(text)

        # Flush final section
        if current_paragraphs:
            sec_text = "\n".join(current_paragraphs)
            length = len(sec_text)
            sections.append(
                ParsedSection(
                    content=sec_text,
                    section_header=current_header,
                    character_start=current_offset,
                    character_end=current_offset + length,
                )
            )
            full_text_parts.append(sec_text)

        full_text = "\n\n".join(full_text_parts)

        return ParsedDocument(
            filename=filename,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            full_text=full_text,
            sections=sections,
            metadata={
                "parser": "DOCXParser",
                "paragraph_count": len(doc.paragraphs),
                "sections_extracted": len(sections),
            },
        )
