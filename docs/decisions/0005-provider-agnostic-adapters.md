# ADR 0005: Provider-Agnostic LLM and Embedding Adapters

## Status
Accepted

## Context
Enterprise AI systems face constant shifts in the vendor ecosystem:
- Changing model pricing, rate limits, and latency profiles (e.g., OpenAI, Anthropic, Google Gemini, Mistral, self-hosted Ollama/vLLM).
- Compliance and data sovereignty mandates requiring on-premises or private VPC deployments.
- Local developer onboarding and continuous integration (CI) environments where external paid API credentials cannot be required or exposed.

Coupling the core application logic to vendor-specific SDKs (e.g., `from openai import OpenAI`) creates technical debt, vendor lock-in, and brittle test suites.

## Decision
We define **Domain-Level Abstract Protocols** for LLM generation and vector embeddings, implemented via pluggable **Infrastructure Adapters**:

### 1. Embedding Adapter Interface (`EmbeddingProvider`)
```python
class EmbeddingProvider(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
    @property
    def model_name(self) -> str: ...
```
Implementations:
- `OpenAICompatibleEmbeddingAdapter`: Works with OpenAI, Azure OpenAI, LiteLLM, Ollama, vLLM.
- `DeterministicMockEmbeddingAdapter`: Generates reproducible, unit-normalized hash-based vector embeddings offline without external network calls.

### 2. LLM Adapter Interface (`LLMProvider`)
```python
class LLMProvider(Protocol):
    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> GenerationResult: ...
    @property
    def model_name(self) -> str: ...
```
Implementations:
- `OpenAICompatibleLLMAdapter`: Works with standard ChatCompletion API formats.
- `DeterministicMockLLMAdapter`: Extracts context citations and crafts predictable, grounded responses or triggers abstention based on configurable rules for offline testing and CI.

### 3. Factory and Dependency Injection
- Provider selection is driven by environment configuration (`EMBEDDING_PROVIDER=mock|openai`, `LLM_PROVIDER=mock|openai`).
- Application services receive the abstract protocol via constructor injection, preventing any direct dependency on concrete SDKs.

## Consequences

### Positive
- **100% Offline Runnable**: Developers and automated CI pipelines run the full RAG lifecycle (ingestion, indexing, hybrid retrieval, synthesis, evaluation) without paid API keys.
- **Vendor Portability**: Switching from OpenAI to self-hosted models or Azure requires updating configuration settings without altering domain or application code.
- **Predictable Testing**: Mock adapters provide deterministic output, enabling rigorous regression testing and citation verification.

### Negative / Trade-offs
- Slight overhead of maintaining adapter wrappers, well justified by the total decoupling from external vendor churn.
