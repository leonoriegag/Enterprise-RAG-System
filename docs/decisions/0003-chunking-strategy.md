# ADR 0003: Document Ingestion and Chunking Strategy

## Status
Accepted

## Context
Retrieval-Augmented Generation relies heavily on the quality and granularity of document chunks:
- **Chunks that are too large** (e.g., > 1,500 tokens) dilute semantic specificity, increase prompt noise, consume excessive context window budget, and obscure exact citations.
- **Chunks that are too small** (e.g., < 100 tokens) lose surrounding context, produce fragmented answers, and fail to provide sufficient information to the generator.
- **Naive fixed-character slicing** splits sentences, numbers, code snippets, and section titles in half, creating nonsensical fragments.
- **Enterprise documents** (PDFs, DOCX, technical manuals, internal wikis) contain structural elements: headers, paragraphs, bulleted lists, and page breaks.

Citations must be verifiable down to document title, chunk index, page number, and section header.

## Decision
We implement a **Hierarchical Structure-Aware Chunking Strategy** with configurable parameters and metadata preservation:

1. **Parser Layer**:
   - Extract raw text alongside structural breadcrumbs: page boundaries (PDF), section headers (Markdown/DOCX), and document-level metadata (author, created date, checksum, MIME type).
2. **Chunking Engine (`RecursiveTokenChunker`)**:
   - Primary chunk target: **512 tokens** (~2,000 characters).
   - Chunk overlap: **64 tokens** (~250 characters) to prevent boundary information loss.
   - Recursive separator hierarchy:
     1. Double newlines (paragraphs / Markdown headers: `\n\n`)
     2. Single newlines (lines / list items: `\n`)
     3. Sentence terminators (`. `, `? `, `! `)
     4. Word boundaries (whitespace ` `)
     5. Raw characters (emergency fallback)
3. **Metadata & Provenance Preservation**:
   Every generated chunk stores:
   - `id`: Deterministic UUID generated from `(document_id, chunk_index)`.
   - `chunk_index`: 0-based sequence number within the document.
   - `page_number`: 1-based page index (for paginated documents like PDF).
   - `section_header`: Nearest preceding heading or structural title.
   - `token_count`: Accurate token measurement.
   - `character_start` / `character_end`: Exact character offsets in normalized source document.
4. **Deduplication & Re-indexing**:
   - Document SHA-256 hash is computed on upload. If identical content is uploaded to the same tenant, redundant parsing and embedding are skipped.
   - Updates trigger atomic replacement of all chunk rows in a single transaction, preventing orphaned chunks.

## Consequences

### Positive
- Preserves natural semantic boundaries, preventing truncated sentences and severed list items.
- High citation precision: generated answers can cite the exact page and section.
- Configurable via application settings (`CHUNK_SIZE`, `CHUNK_OVERLAP`) without modifying core pipeline code.
- Idempotent and deterministic: re-indexing the same document produces identical chunk structures.

### Negative / Trade-offs
- More compute intensive than fixed character slicing, but negligible (< 100ms per typical enterprise document) compared to embedding generation.
