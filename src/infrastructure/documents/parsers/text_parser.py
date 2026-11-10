"""Plain text document parser."""

from src.domain.interfaces.parsers import ParsedDocument, ParsedSection


class TextParser:
    """Extracts text content from plain text files."""

    SUPPORTED_MIME_TYPES = {"text/plain"}

    def can_parse(self, mime_type: str) -> bool:
        return mime_type.lower().split(";")[0].strip() in self.SUPPORTED_MIME_TYPES

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")

        section = ParsedSection(
            content=text,
            character_start=0,
            character_end=len(text),
        )

        return ParsedDocument(
            filename=filename,
            mime_type="text/plain",
            full_text=text,
            sections=[section],
            metadata={"parser": "TextParser"},
        )
