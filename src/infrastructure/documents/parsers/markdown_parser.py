"""Markdown document parser with structural heading extraction."""

import re

from src.domain.interfaces.parsers import ParsedDocument, ParsedSection


class MarkdownParser:
    """Extracts sections and headers from Markdown documents."""

    SUPPORTED_MIME_TYPES = {"text/markdown", "text/x-markdown"}
    _HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def can_parse(self, mime_type: str) -> bool:
        return mime_type.lower().split(";")[0].strip() in self.SUPPORTED_MIME_TYPES

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            full_text = content.decode("utf-8")
        except UnicodeDecodeError:
            full_text = content.decode("latin-1", errors="replace")

        sections: list[ParsedSection] = []
        heading_matches = list(self._HEADING_REGEX.finditer(full_text))

        if not heading_matches:
            # No headings found, treat entire document as single section
            sections.append(
                ParsedSection(
                    content=full_text,
                    character_start=0,
                    character_end=len(full_text),
                )
            )
        else:
            # Document has leading content before first heading?
            if heading_matches[0].start() > 0:
                preamble = full_text[: heading_matches[0].start()].strip()
                if preamble:
                    sections.append(
                        ParsedSection(
                            content=preamble,
                            section_header="Overview",
                            character_start=0,
                            character_end=heading_matches[0].start(),
                        )
                    )

            for i, match in enumerate(heading_matches):
                heading_level = len(match.group(1))
                heading_title = match.group(2).strip()

                start_idx = match.start()
                if i + 1 < len(heading_matches):
                    end_idx = heading_matches[i + 1].start()
                else:
                    end_idx = len(full_text)
                section_text = full_text[start_idx:end_idx].strip()

                sections.append(
                    ParsedSection(
                        content=section_text,
                        section_header=f"H{heading_level}: {heading_title}",
                        character_start=start_idx,
                        character_end=end_idx,
                    )
                )

        return ParsedDocument(
            filename=filename,
            mime_type="text/markdown",
            full_text=full_text,
            sections=sections,
            metadata={
                "parser": "MarkdownParser",
                "headings_detected": len(heading_matches),
            },
        )
