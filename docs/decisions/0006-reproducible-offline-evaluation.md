# ADR 0006: Reproducible Offline Evaluation Framework

## Status
Accepted

## Context
A major challenge in Enterprise RAG engineering is evaluating retrieval and generation quality objectively and reproducibly:
1. **Flaky Evaluations**: Relying on live LLM judges ("LLM-as-a-judge") across entire test suites introduces non-determinism, API rate limits, non-trivial recurring financial cost, and vulnerability to prompt drift.
2. **Conflated Failure Modes**: When a user receives an incorrect answer, traditional evaluations often fail to distinguish between:
   - Retrieval failure (the relevant chunk was never retrieved),
   - Ranking failure (the relevant chunk was retrieved but ranked too low),
   - Generation failure (the chunk was provided in context, but the LLM ignored or hallucinated beyond it),
   - Authorization failure (the user was legitimately blocked from viewing the source document).
3. **Security Failures**: Standard RAG benchmarks (e.g., RAGAS, TruLens) focus on generic Q&A without testing enterprise-critical failure modes such as tenant isolation breaches, prompt injection through retrieved context, and out-of-scope abstention.

## Decision
We implement a **Dual-Tier Offline Evaluation Suite**:

### Tier 1: Deterministic Benchmark Suite (Default / CI)
- **Zero API dependency**: Runs entirely locally against pre-seeded ACME Enterprise fixtures and deterministic mock or local vector engines.
- **Isolated Component Metrics**:
  - **Retrieval Metrics**:
    - **Recall@K**: Proportion of expected chunks/documents retrieved within top-$K$ candidates.
    - **Precision@K**: Proportion of top-$K$ retrieved candidates that are relevant.
    - **MRR (Mean Reciprocal Rank)**: $MRR = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$ assessing how high the first relevant chunk appears.
    - **nDCG@K (Normalized Discounted Cumulative Gain)**: Grading ranking quality for multi-evidence queries.
  - **Generation & Citation Metrics**:
    - **Citation Precision & Coverage**: Verifies that 100% of generated citation tags `[Doc-X:Chunk-Y]` map to valid, retrieved chunks in the context.
    - **Abstention Accuracy**: Measures the system's ability to explicitly refuse to answer when evidence is absent or insufficient, rather than hallucinating.
  - **Security & Authorization Metrics**:
    - **Tenant Isolation Rate**: Must be strictly 100% (0 cross-tenant leaks allowed across all test queries).
    - **Department Access Conformance**: Verifies that restricted documents are completely excluded from unauthorized users' retrieval sets.
    - **Prompt Injection Resilience**: Evaluates adversarial documents attempting to hijack system instructions.

### Tier 2: Model-Based Quality Evaluation (Optional / Staging)
- Optional offline runner using real LLM judges for natural language faithfulness and semantic answer similarity against golden answers.
- Kept strictly decoupled from the core automated test suite to maintain fast, reproducible CI builds.

## Consequences

### Positive
- Tests can run on every Git commit, pull request, or local development workflow without internet access or API tokens.
- Clear diagnostic attribution: failures point directly to indexing, retrieval scoring, context assembly, or generator behavior.
- Rigorous security assertions provide mathematical proof of multi-tenant safety.

### Negative / Trade-offs
- Deterministic evaluation requires maintaining curated ground-truth query-document pairs in `examples/dataset/`. We provide a comprehensive ACME Enterprise evaluation dataset out-of-the-box.
