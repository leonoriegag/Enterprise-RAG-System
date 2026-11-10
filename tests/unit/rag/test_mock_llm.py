"""Unit tests for DeterministicMockLLMAdapter."""

import pytest

from src.infrastructure.llm.mock_adapter import ABSTENTION_MESSAGE, DeterministicMockLLMAdapter


@pytest.mark.asyncio
async def test_mock_llm_synthesizes_grounded_answer_with_citations() -> None:
    adapter = DeterministicMockLLMAdapter()

    user_prompt = """
<retrieved_context>
<source 1>
Document: Leave Policy
Content: Full-time employees accrue 20 vacation days annually. Unused leave rolls over up to 5 days.
</source 1>
</retrieved_context>

<user_question>
How many vacation days do full-time employees accrue?
</user_question>
"""

    result = await adapter.generate_response(
        system_prompt="System rules.",
        user_prompt=user_prompt,
    )

    assert result.finish_reason == "stop"
    assert "20 vacation days" in result.content
    assert "[1]" in result.content
    assert result.did_abstain is False


@pytest.mark.asyncio
async def test_mock_llm_abstains_when_no_context_provided() -> None:
    adapter = DeterministicMockLLMAdapter()

    user_prompt = """
<retrieved_context>
</retrieved_context>

<user_question>
What is the company mission?
</user_question>
"""

    result = await adapter.generate_response(
        system_prompt="System rules.",
        user_prompt=user_prompt,
    )

    assert result.did_abstain is True
    assert result.finish_reason == "abstain"
    assert result.content == ABSTENTION_MESSAGE


@pytest.mark.asyncio
async def test_mock_llm_multiple_sources() -> None:
    adapter = DeterministicMockLLMAdapter()

    user_prompt = """
<retrieved_context>
<source 1>
Document: Security Standard
Content: Passwords must be at least 14 characters long.
</source 1>

<source 2>
Document: Network Guide
Content: Passwords must not contain personal names.
</source 2>
</retrieved_context>

<user_question>
What are the passwords requirements?
</user_question>
"""

    result = await adapter.generate_response(
        system_prompt="System rules.",
        user_prompt=user_prompt,
    )

    assert result.finish_reason == "stop"
    assert "[1]" in result.content or "[2]" in result.content
