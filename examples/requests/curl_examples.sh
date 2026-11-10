#!/usr/bin/env bash
# ==============================================================================
# Enterprise RAG System — cURL Examples Script
# Demonstrates health probes, auth, ingestion, hybrid retrieval, and grounded RAG.
# ==============================================================================

set -euo pipefail

BASE_URL="http://localhost:8000"

echo "=== 1. Health Liveness & Readiness ==="
curl -s -X GET "${BASE_URL}/health" | jq .
curl -s -X GET "${BASE_URL}/health/ready" | jq .

echo -e "\n=== 2. Authenticating as Admin (admin@acme.corp) ==="
ADMIN_TOKEN=$(curl -s -X POST "${BASE_URL}/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@acme.corp",
    "password": "AcmeDemo2026!",
    "tenant_slug": "acme"
  }' | jq -r .access_token)

echo "Acquired Admin JWT: ${ADMIN_TOKEN:0:20}..."

echo -e "\n=== 3. Authenticating as HR Specialist (hr.specialist@acme.corp) ==="
HR_TOKEN=$(curl -s -X POST "${BASE_URL}/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "hr.specialist@acme.corp",
    "password": "AcmeDemo2026!",
    "tenant_slug": "acme"
  }' | jq -r .access_token)

echo "Acquired HR JWT: ${HR_TOKEN:0:20}..."

echo -e "\n=== 4. Check Current User Claims (/api/v1/auth/me) ==="
curl -s -X GET "${BASE_URL}/api/v1/auth/me" \
  -H "Authorization: Bearer ${HR_TOKEN}" | jq .

echo -e "\n=== 5. List Documents for Tenant ==="
curl -s -X GET "${BASE_URL}/api/v1/documents?limit=5" \
  -H "Authorization: Bearer ${HR_TOKEN}" | jq .

echo -e "\n=== 6. Hybrid Search (Semantic + Lexical RRF) ==="
curl -s -X POST "${BASE_URL}/api/v1/retrieval/search" \
  -H "Authorization: Bearer ${HR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many days of paid time off can be rolled over?",
    "department": "hr",
    "top_k": 3
  }' | jq .

echo -e "\n=== 7. Grounded RAG Question Answering with Citations ==="
curl -s -X POST "${BASE_URL}/api/v1/rag/ask" \
  -H "Authorization: Bearer ${HR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the maximum number of unused PTO days an employee can carry over into the next year?",
    "department": "hr",
    "top_k": 5
  }' | jq .

echo -e "\n=== 8. Honest Abstention (Unanswerable topic) ==="
curl -s -X POST "${BASE_URL}/api/v1/rag/ask" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the quantum encryption protocol planned for Martian satellites?",
    "top_k": 5
  }' | jq .

echo -e "\n=== 9. Admin RBAC Test: Non-Admin call rejected with 403 ==="
curl -s -w "\nHTTP Status: %{http_code}\n" -X GET "${BASE_URL}/api/v1/admin/users" \
  -H "Authorization: Bearer ${HR_TOKEN}" | jq . || true

echo -e "\n=== Examples completed successfully ==="
