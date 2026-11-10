"""Document upload validator with MIME, size, and magic byte verification."""

from dataclasses import dataclass

from src.domain.exceptions import IngestionError


@dataclass(frozen=True)
class FileValidationResult:
    """Result of file validation."""

    is_valid: bool
    mime_type: str
    file_size_bytes: int
    detected_format: str


class DocumentValidator:
    """Validates uploaded files for size, allowed MIME types, and binary signatures."""

    ALLOWED_MIME_TYPES = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "text/markdown": "md",
        "text/x-markdown": "md",
    }

    MAGIC_SIGNATURES: dict[str, bytes] = {
        "pdf": b"%PDF-",
        "docx": b"PK\x03\x04",
    }

    def __init__(self, max_size_mb: int = 25) -> None:
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def validate(self, content: bytes, filename: str, declared_mime: str) -> FileValidationResult:
        """Validate file size, declared MIME, and binary magic bytes."""
        file_size = len(content)

        if file_size == 0:
            raise IngestionError(f"Uploaded file '{filename}' is empty (0 bytes).")

        if file_size > self.max_size_bytes:
            mb_size = file_size / (1024 * 1024)
            limit_mb = self.max_size_bytes / (1024 * 1024)
            msg = f"File '{filename}' ({mb_size:.2f} MB) exceeds maximum allowed {limit_mb:.0f} MB."
            raise IngestionError(msg)

        # Normalize declared MIME type
        normalized_mime = declared_mime.lower().split(";")[0].strip()
        format_name = self.ALLOWED_MIME_TYPES.get(normalized_mime)

        if not format_name:
            # Fall back to file extension inspection
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            ext_map = {"pdf": "pdf", "docx": "docx", "txt": "txt", "md": "md", "markdown": "md"}
            format_name = ext_map.get(ext)
            if not format_name:
                allowed = ", ".join(sorted(set(self.ALLOWED_MIME_TYPES.keys())))
                msg = (
                    f"Unsupported format for '{filename}'. Declared MIME: '{declared_mime}'. "
                    f"Allowed: {allowed}"
                )
                raise IngestionError(msg)

        # Magic byte verification for binary formats
        if format_name in self.MAGIC_SIGNATURES:
            expected_magic = self.MAGIC_SIGNATURES[format_name]
            if not content.startswith(expected_magic):
                msg = f"File '{filename}' claims format '{format_name}' but lacks magic signature."
                raise IngestionError(msg)
        elif format_name in ("txt", "md"):
            # Check text decodability
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as err:
                try:
                    content.decode("latin-1")
                except Exception as ex:
                    raise IngestionError(
                        f"Text file '{filename}' contains invalid un-decodable bytes: {err}"
                    ) from ex

        return FileValidationResult(
            is_valid=True,
            mime_type=normalized_mime,
            file_size_bytes=file_size,
            detected_format=format_name,
        )
