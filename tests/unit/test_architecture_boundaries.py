"""Architecture boundary tests verifying Clean Architecture layer separation."""

import ast
from pathlib import Path


def get_imports(file_path: Path) -> list[str]:
    """Parse a Python source file and extract all imported module names."""
    imports: list[str] = []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def test_domain_layer_has_zero_outer_dependencies() -> None:
    """Domain layer must NEVER import from application, infrastructure, or interfaces."""
    src_dir = Path(__file__).parent.parent.parent / "src"
    domain_dir = src_dir / "domain"

    forbidden_prefixes = (
        "src.application",
        "src.infrastructure",
        "src.interfaces",
        "sqlalchemy",
        "fastapi",
        "asyncpg",
        "pgvector",
        "pydantic_settings",
        "openai",
    )

    for py_file in domain_dir.rglob("*.py"):
        imports = get_imports(py_file)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                assert not imp.startswith(forbidden), (
                    f"Architectural boundary violation in {py_file.name}: "
                    f"Domain layer imports forbidden module '{imp}'"
                )


def test_application_layer_does_not_import_infrastructure() -> None:
    """Application layer must NOT import from infrastructure or interfaces directly."""
    src_dir = Path(__file__).parent.parent.parent / "src"
    app_dir = src_dir / "application"

    forbidden_prefixes = (
        "src.infrastructure",
        "src.interfaces",
        "sqlalchemy",
        "asyncpg",
        "pgvector",
    )

    for py_file in app_dir.rglob("*.py"):
        imports = get_imports(py_file)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                assert not imp.startswith(forbidden), (
                    f"Architectural boundary violation in {py_file.name}: "
                    f"Application layer imports forbidden module '{imp}'"
                )
