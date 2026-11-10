"""Re-export shim — DocumentValidator lives in the domain layer.

Keeping this module prevents import breakage in any external code that
referenced the old infrastructure path, while ensuring the application
layer correctly imports from src.domain.services.validator.
"""

from src.domain.services.validator import DocumentValidator, FileValidationResult

__all__ = ["DocumentValidator", "FileValidationResult"]
