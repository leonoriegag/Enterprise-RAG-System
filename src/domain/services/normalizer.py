"""Text normalization service for sanitizing document contents."""

import re
import unicodedata


class TextNormalizer:
    """Sanitizes and normalizes extracted text across various document formats."""

    # Remove non-printable control characters except newline and tab
    _CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    # Collapse multiple consecutive horizontal whitespaces into single space
    _HORIZONTAL_WHITESPACE_REGEX = re.compile(r"[^\S\r\n]+")
    # Collapse 3 or more consecutive newlines into 2 (preserve paragraph breaks)
    _EXCESSIVE_NEWLINES_REGEX = re.compile(r"\n{3,}")

    @classmethod
    def normalize(cls, text: str) -> str:
        """Apply Unicode NFKC normalization, strip invalid controls, and normalize whitespace."""
        if not text:
            return ""

        # Unicode compatibility decomposition & canonical composition
        text = unicodedata.normalize("NFKC", text)

        # Remove null bytes and non-printable control characters
        text = cls._CONTROL_CHARS_REGEX.sub("", text)

        # Normalize line endings to standard Unix \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse excessive horizontal spaces within lines
        lines = [
            cls._HORIZONTAL_WHITESPACE_REGEX.sub(" ", line).strip() for line in text.split("\n")
        ]
        text = "\n".join(lines)

        # Collapse excessive blank lines
        text = cls._EXCESSIVE_NEWLINES_REGEX.sub("\n\n", text)

        return text.strip()
