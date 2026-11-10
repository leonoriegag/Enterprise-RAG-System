# Development & Local Setup Guide

## 1. Prerequisites

- **Python 3.12+**
- **Docker & Docker Compose** (for PostgreSQL + pgvector)
- **Git**

---

## 2. Quickstart: 5-Minute Local Setup

### Step 1: Clone & Environment Configuration

```bash
git clone https://github.com/leonoriegag/Enterprise-RAG-System.git
cd Enterprise-RAG-System

# Create local environment file from example
cp .env.example .env
```

### Step 2: Start PostgreSQL with pgvector

```bash
docker compose up -d db
```

Wait 5 seconds for PostgreSQL to initialize healthy status.

### Step 3: Set Up Python Virtual Environment

```bash
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install project with development dependencies
pip install -e ".[dev]"
```

### Step 4: Run Database Migrations & Seed Sample Data

```bash
# Apply Alembic schema migrations
alembic upgrade head

# Seed ACME Enterprise demonstration tenants, users, and documents
python -m src.interfaces.cli seed
```

### Step 5: Start the API Server

```bash
uvicorn src.interfaces.api.main:app --reload --port 8000
```

Access the interactive OpenAPI Swagger documentation at:
**http://localhost:8000/docs**

---

## 3. Offline Demonstration Mode

The system is engineered to run **100% offline** without external API keys or recurring cloud costs.

In `.env`:
```env
EMBEDDING_PROVIDER=mock
LLM_PROVIDER=mock
MOCK_EMBEDDING_DIM=384
```

When running in offline mode:
- **`DeterministicMockEmbeddingAdapter`**: Computes unit-normalized deterministic hash vectors for queries and documents. Semantic similarity between related tokens is preserved through deterministic seed dictionaries.
- **`DeterministicMockLLMAdapter`**: Analyzes the retrieved context, extracts relevant sentences, constructs grounded responses with valid `[1]`, `[2]` citation markers, or triggers genuine abstention when evidence is missing.

To switch to real LLM providers, simply update `.env`:
```env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

---

## 4. Code Quality & Testing Standards

### Automated Testing

```bash
# Run all fast unit and boundary tests (no external services needed)
pytest tests/unit/

# Run database integration tests (requires PostgreSQL container)
pytest tests/integration/

# Run security, RLS, and prompt injection tests
pytest tests/security/

# Run deterministic evaluation benchmark suite
pytest tests/evaluation/

# Run all test suites with coverage
pytest --cov=src --cov-report=term-missing
```

### Linting & Formatting

We use **Ruff** for high-speed Python linting and formatting:

```bash
# Format code
ruff format .

# Check linting rules
ruff check . --fix
```

### Static Type Checking

We enforce strict type hints with **mypy**:

```bash
mypy src/
```

### Architecture Boundary Tests

We enforce Clean Architecture layer rules via automated tests (`tests/unit/test_architecture_boundaries.py`):
- `src/domain/` may **never** import from `src/infrastructure/`, `src/application/`, or `src/interfaces/`.
- `src/application/` may **never** import from `src/infrastructure/` or `src/interfaces/`.
- All database dependencies and third-party AI SDKs are strictly confined to `src/infrastructure/`.
