"""Tests for /health and /health/ready monitoring endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_endpoint_returns_200(client: AsyncClient) -> None:
    """GET /health must return immediate HTTP 200 with healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "test"
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_readiness_endpoint_probes_dependencies(client: AsyncClient) -> None:
    """GET /health/ready must probe database, embedding provider, and LLM status."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "components" in data
    assert "database" in data["components"]
    assert "embedding_provider" in data["components"]
    assert "llm_provider" in data["components"]
    assert data["components"]["database"]["status"] == "healthy"
