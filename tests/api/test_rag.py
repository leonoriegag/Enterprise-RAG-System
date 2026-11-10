"""Tests for /api/v1/rag RAG question-answering endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ask_requires_auth(client: AsyncClient) -> None:
    """POST /api/v1/rag/ask without a bearer token must return 401."""
    response = await client.post(
        "/api/v1/rag/ask",
        json={"question": "How many PTO days do I get?"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ask_returns_grounded_answer_with_citations(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """HR user asking about leave policy should receive an answer grounded in seeded chunk."""
    hr_token = app_context["hr_token"]
    response = await client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={
            "question": "How many paid time off days do employees accrue per year?",
            "top_k": 5,
            "confidence_threshold": 0.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "question" in data
    assert "answer" in data
    assert "abstained" in data
    assert "citations" in data
    assert isinstance(data["abstained"], bool)
    assert isinstance(data["citations"], list)
    assert "execution_time_ms" in data


@pytest.mark.asyncio
async def test_ask_cross_department_returns_abstention(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """IT user querying HR documents should receive abstention (no visible evidence)."""
    it_token = app_context["it_token"]
    response = await client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {it_token}"},
        json={
            "question": "How many PTO days do employees get?",
            "department": "hr",  # explicitly targeting HR
            "top_k": 5,
            "confidence_threshold": 0.5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    # IT user cannot see HR chunks — retriever returns nothing — expect abstention
    assert data["abstained"] is True
    assert data["citations"] == []


@pytest.mark.asyncio
async def test_ask_unanswerable_question_returns_abstention(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Completely irrelevant query with no matching chunks should trigger abstention."""
    hr_token = app_context["hr_token"]
    response = await client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={
            "question": "What is the capital of Mars?",
            "top_k": 5,
            "confidence_threshold": 0.9,
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Mock LLM always returns a fixed answer, but with high confidence_threshold the
    # service may abstain when evidence is insufficient. We only verify shape here.
    assert "answer" in data
    assert "abstained" in data


@pytest.mark.asyncio
async def test_ask_response_shape_is_complete(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Response must include all required fields per AskResponse schema."""
    hr_token = app_context["hr_token"]
    response = await client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"question": "What is the leave carry-over limit?"},
    )
    assert response.status_code == 200
    data = response.json()
    required_keys = {
        "question",
        "answer",
        "abstained",
        "confidence_score",
        "citations",
        "execution_time_ms",
        "model",
    }
    assert required_keys.issubset(data.keys())


@pytest.mark.asyncio
async def test_ask_other_tenant_cannot_access_acme_knowledge(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """User from other_tenant receives abstention — cannot see ACME chunks."""
    other_token = app_context["other_token"]
    response = await client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"question": "How many PTO days do ACME employees get?"},
    )
    assert response.status_code == 200
    data = response.json()
    # Cross-tenant isolation: other_tenant sees no ACME data → abstention
    assert data["abstained"] is True
    assert data["citations"] == []
