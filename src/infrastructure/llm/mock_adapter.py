"""Deterministic mock LLM adapter for offline testing and deterministic CI pipelines."""

from __future__ import annotations

import re

from src.domain.interfaces.llm import GenerationResult
from src.shared.logging import get_logger

logger = get_logger(__name__)

ABSTENTION_MESSAGE = (
    "I cannot answer this question based on the provided documents. "
    "No sufficiently relevant content was found in the knowledge base."
)


class DeterministicMockLLMAdapter:
    """
    Offline LLM adapter extracting sentences from prompt sources matching query keywords.

    Behavior:
    - Parses source blocks from the prompt (e.g., <source N>...</source N>).
    - Extracts non-stopword keywords from user question.
    - Scores sentences in each source block by keyword overlap.
    - Constructs answer using best sentences followed by citation markers [N].
    - Returns deterministic abstention if no sources exist or no matching sentences match.
    """

    STOP_WORDS = frozenset(
        {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "on",
            "at",
            "by",
            "for",
            "with",
            "about",
            "as",
            "into",
            "from",
            "and",
            "or",
            "but",
            "not",
            "this",
            "that",
            "it",
            "its",
            "their",
            "our",
            "what",
            "which",
            "who",
            "how",
            "when",
            "where",
            "why",
            "tell",
            "me",
        }
    )

    def __init__(
        self,
        model_name: str = "mock-deterministic-llm",
        max_sentences_per_source: int = 2,
    ) -> None:
        self._model_name = model_name
        self.max_sentences_per_source = max_sentences_per_source

    @property
    def model_name(self) -> str:
        """Name of the mock LLM model."""
        return self._model_name

    def _extract_keywords(self, query: str) -> set[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
        return {t for t in tokens if t not in self.STOP_WORDS and len(t) > 2}

    def _extract_sources(self, user_prompt: str) -> list[tuple[int, str]]:
        """Extract indexed source blocks from user prompt."""
        # If <retrieved_context> tags are present, search strictly within them
        context_match = re.search(
            r"<retrieved_context>(.*?)</retrieved_context>", user_prompt, re.DOTALL | re.IGNORECASE
        )
        if context_match:
            context_text = context_match.group(1).strip()
            if not context_text:
                return []
            pattern = re.compile(r"<source\s+(\d+)>(.*?)</source\s+\1>", re.DOTALL | re.IGNORECASE)
            matches = pattern.findall(context_text)
            return [(int(idx), content.strip()) for idx, content in matches]

        # Find all <source N>content</source N> patterns anywhere in prompt
        pattern = re.compile(r"<source\s+(\d+)>(.*?)</source\s+\1>", re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(user_prompt)
        if matches:
            return [(int(idx), content.strip()) for idx, content in matches]

        # If user explicitly asked a question without context tags or sources, return empty
        if "<user_question>" in user_prompt:
            return []

        # Fallback: treat prompt as raw content block #1
        return [(1, user_prompt.strip())]

    def _extract_question(self, user_prompt: str) -> str:
        """Extract question from <user_question> tags or entire prompt."""
        match = re.search(r"<user_question>(.*?)</user_question>", user_prompt, re.DOTALL)
        if match:
            return match.group(1).strip()
        return user_prompt.strip()

    def _score_sentence(self, sentence: str, keywords: set[str]) -> int:
        words = set(re.findall(r"[a-zA-Z0-9]+", sentence.lower()))
        return len(words & keywords)

    def _select_sentences(self, text: str, keywords: set[str]) -> list[str]:
        """Select top scoring sentences from source text."""
        # Split text into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        scored = [(self._score_sentence(s, keywords), s) for s in sentences]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for score, s in scored[: self.max_sentences_per_source] if score > 0]

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Synthesize a deterministic response from prompt context and question."""
        question = self._extract_question(user_prompt)
        keywords = self._extract_keywords(question)
        sources = self._extract_sources(user_prompt)

        # Check if prompt specifically indicates no context
        if not sources or "<retrieved_context></retrieved_context>" in user_prompt:
            return GenerationResult(
                content=ABSTENTION_MESSAGE,
                prompt_tokens=len(user_prompt.split()),
                completion_tokens=len(ABSTENTION_MESSAGE.split()),
                model_name=self.model_name,
                finish_reason="abstain",
            )

        answer_parts: list[str] = []
        for idx, source_content in sources:
            matching_sentences = self._select_sentences(source_content, keywords)
            if matching_sentences:
                combined_text = " ".join(matching_sentences)
                answer_parts.append(f"{combined_text} [{idx}]")

        if not answer_parts:
            # If no sentences matched keywords, but sources exist and question is broad,
            # take the first sentence from source 1 if present
            if sources and sources[0][1]:
                first_source_sentences = [
                    s.strip() for s in re.split(r"(?<=[.!?])\s+", sources[0][1]) if s.strip()
                ]
                if first_source_sentences:
                    answer_parts.append(f"{first_source_sentences[0]} [1]")

        if not answer_parts:
            return GenerationResult(
                content=ABSTENTION_MESSAGE,
                prompt_tokens=len(user_prompt.split()),
                completion_tokens=len(ABSTENTION_MESSAGE.split()),
                model_name=self.model_name,
                finish_reason="abstain",
            )

        full_answer = " ".join(answer_parts)
        prompt_tokens = len(system_prompt.split()) + len(user_prompt.split())
        completion_tokens = len(full_answer.split())

        return GenerationResult(
            content=full_answer,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_name=self.model_name,
            finish_reason="stop",
        )
