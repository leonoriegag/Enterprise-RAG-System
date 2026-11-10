"""Document parsers package."""

from src.infrastructure.documents.parsers.docx_parser import DOCXParser
from src.infrastructure.documents.parsers.factory import ParserRegistry
from src.infrastructure.documents.parsers.markdown_parser import MarkdownParser
from src.infrastructure.documents.parsers.pdf_parser import PDFParser
from src.infrastructure.documents.parsers.text_parser import TextParser

__all__ = [
    "ParserRegistry",
    "PDFParser",
    "DOCXParser",
    "MarkdownParser",
    "TextParser",
]
