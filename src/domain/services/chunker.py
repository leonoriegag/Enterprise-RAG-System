"""Structure-preserving recursive token chunker."""

from typing import Any

from src.domain.interfaces.chunker import RawChunk
from src.domain.interfaces.parsers import ParsedDocument, ParsedSection
from src.domain.services.normalizer import TextNormalizer


class RecursiveTokenChunker:
    """Splits parsed documents into overlapping chunks with section and page provenance."""

    def __init__(
        self,
        default_chunk_size: int = 512,
        default_overlap: int = 64,
        chars_per_token: float = 4.0,
    ) -> None:
        self.default_chunk_size = default_chunk_size
        self.default_overlap = default_overlap
        self.chars_per_token = chars_per_token
        self.separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from character length using empirical ratio."""
        if not text:
            return 0
        return max(1, int(len(text) / self.chars_per_token))

    def chunk(
        self,
        document: ParsedDocument,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> list[RawChunk]:
        """Split a parsed document into structured chunks."""
        effective_chunk_size = chunk_size or self.default_chunk_size
        effective_overlap = overlap if overlap is not None else self.default_overlap

        # Convert token budgets to character bounds
        target_chars = int(effective_chunk_size * self.chars_per_token)
        overlap_chars = int(effective_overlap * self.chars_per_token)

        raw_chunks: list[RawChunk] = []
        global_chunk_index = 0

        # If document has no explicit sections, treat full_text as a single section
        sections = document.sections
        if not sections and document.full_text:
            sections = [ParsedSection(content=document.full_text)]

        for section in sections:
            normalized_content = TextNormalizer.normalize(section.content)
            if not normalized_content:
                continue

            section_slices = self._split_text(
                text=normalized_content,
                target_chars=target_chars,
                overlap_chars=overlap_chars,
                separators=self.separators,
            )

            current_char_offset = section.character_start
            for text_slice in section_slices:
                cleaned_slice = text_slice.strip()
                if not cleaned_slice:
                    continue

                token_count = self.estimate_tokens(cleaned_slice)
                slice_len = len(cleaned_slice)

                metadata: dict[str, Any] = {
                    "filename": document.filename,
                    "mime_type": document.mime_type,
                }
                if section.section_header:
                    metadata["section_header"] = section.section_header
                if section.page_number is not None:
                    metadata["page_number"] = section.page_number

                raw_chunks.append(
                    RawChunk(
                        chunk_index=global_chunk_index,
                        content=cleaned_slice,
                        token_count=token_count,
                        page_number=section.page_number,
                        section_header=section.section_header,
                        character_start=current_char_offset,
                        character_end=current_char_offset + slice_len,
                        metadata=metadata,
                    )
                )
                global_chunk_index += 1
                current_char_offset += slice_len

        return raw_chunks

    def _split_text(
        self,
        text: str,
        target_chars: int,
        overlap_chars: int,
        separators: list[str],
    ) -> list[str]:
        """Recursively split text until all slices are within target_chars."""
        if len(text) <= target_chars:
            return [text]

        # Find best separator present in the text
        selected_sep = ""
        for sep in separators:
            if sep == "":
                selected_sep = ""
                break
            if sep in text:
                selected_sep = sep
                break

        if selected_sep == "":
            # Character-level fallback split with overlap
            step = max(1, target_chars - overlap_chars)
            return [text[i : i + target_chars] for i in range(0, len(text), step)]

        # Split into initial parts
        parts = text.split(selected_sep)
        combined_slices: list[str] = []
        current_buffer: list[str] = []
        current_len = 0

        for part in parts:
            part_len = len(part) + len(selected_sep)

            # If an individual part itself is larger than target_chars, recursively split it
            if len(part) > target_chars:
                if current_buffer:
                    combined_slices.append(selected_sep.join(current_buffer))
                    current_buffer = []
                    current_len = 0

                sub_separators = separators[separators.index(selected_sep) + 1 :]
                sub_slices = self._split_text(part, target_chars, overlap_chars, sub_separators)
                combined_slices.extend(sub_slices)
                continue

            if current_len + part_len > target_chars and current_buffer:
                combined_slices.append(selected_sep.join(current_buffer))

                # Build overlap from tail of current_buffer
                overlap_buffer: list[str] = []
                overlap_accum = 0
                for prev in reversed(current_buffer):
                    if overlap_accum + len(prev) + len(selected_sep) <= overlap_chars:
                        overlap_buffer.insert(0, prev)
                        overlap_accum += len(prev) + len(selected_sep)
                    else:
                        break

                current_buffer = overlap_buffer
                current_len = sum(len(p) + len(selected_sep) for p in current_buffer)

            current_buffer.append(part)
            current_len += part_len

        if current_buffer:
            combined_slices.append(selected_sep.join(current_buffer))

        return combined_slices
