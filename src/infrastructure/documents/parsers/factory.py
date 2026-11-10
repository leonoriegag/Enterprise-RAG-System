"""Parser registry and factory for document extraction."""

from src.domain.exceptions import IngestionError
from src.domain.interfaces.parsers import DocumentParser
from src.infrastructure.documents.parsers.docx_parser import DOCXParser
from src.infrastructure.documents.parsers.markdown_parser import MarkdownParser
from src.infrastructure.documents.parsers.pdf_parser import PDFParser
from src.infrastructure.documents.parsers.text_parser import TextParser


class ParserRegistry:
    """Registry maintaining available document parsers."""

    def __init__(self) -> None:
        self.parsers: list[DocumentParser] = [
            PDFParser(),
            DOCXParser(),
            MarkdownParser(),
            TextParser(),
        ]

    def get_parser(self, mime_type: str, filename: str = "") -> DocumentParser:
        """Find the matching parser for the given MIME type or file extension."""
        for parser in self.parsers:
            if parser.can_parse(mime_type):
                return parser

        # Fallback to extension mapping
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        ext_to_mime = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "md": "text/markdown",
            "markdown": "text/markdown",
        }
        mapped_mime = ext_to_mime.get(ext)
        if mapped_mime:
            for parser in self.parsers:
                if parser.can_parse(mapped_mime):
                    return parser

        msg = f"No parser available for MIME type '{mime_type}' (filename: '{filename}')."
        raise IngestionError(msg)
