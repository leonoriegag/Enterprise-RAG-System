# ADR 0004: Enterprise Multi-Tenancy and Row-Level Security (RLS)

## Status
Accepted

## Context
In an enterprise RAG system, confidentiality and strict tenant isolation are non-negotiable requirements:
1. **Multi-Tenant Isolation**: ACME Enterprise hosts multiple client organizations, internal subsidiaries, or independent business units. Under no circumstances may data from Tenant A be visible, retrievable, or synthesizable for Tenant B.
2. **Document-Level Access Control**: Within a single tenant, access must respect organizational structure:
   - Department boundaries (e.g., HR, Finance, Engineering, Legal).
   - Classification levels (e.g., `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`).
   - Role-Based Access Control (e.g., `admin`, `manager`, `member`, `guest`).
3. **Defense-in-Depth vs. Application Filter Fragility**: Relying solely on `WHERE tenant_id = ?` clauses in application code is prone to developer error, where a single forgotten filter or joined query can lead to catastrophic data leakage.

## Decision
We implement a **Dual-Layer Defense-in-Depth Security Architecture**:

### 1. Database-Enforced Row-Level Security (PostgreSQL RLS)
- Enable `ROW LEVEL SECURITY` on all core multi-tenant tables: `documents`, `document_chunks`, `queries`, and `audit_logs`.
- Define database policies using PostgreSQL session variables:
  ```sql
  CREATE POLICY tenant_isolation_policy ON document_chunks
      FOR ALL
      USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
  ```
- Application database sessions set `SET LOCAL app.current_tenant_id = :tenant_id` at the start of each transaction or through an asynchronous SQLAlchemy session hook.
- Even if an application query omits an explicit tenant filter, the database engine enforces isolation at the storage level, eliminating data leakage vulnerabilities.

### 2. Application-Level Server-Side Authorization Context
- The tenant and user identity are extracted strictly from verified JWT tokens or authenticated session headers, never from client-provided query parameters.
- Document-level permission evaluation combines:
  - **Tenant check**: `user.tenant_id == document.tenant_id`
  - **Classification check**: User role clearance vs. document classification level.
  - **Department check**: Cross-department access policies (e.g., `HR` restricted documents are only retrievable by members of the `HR` department or tenant `admin`).
- **Pre-Retrieval Filtering**: Authorization filters are translated into SQL `WHERE` criteria and applied *before* vector and full-text scoring. Unauthorized chunks are never loaded into memory, never reranked, and never passed to the LLM.

## Consequences

### Positive
- **Guaranteed Isolation**: Hardware/kernel and database engine guarantees prevent cross-tenant data leaks even under buggy application queries.
- **Auditability**: RLS policies are declarative, centralized, and subject to direct automated SQL security unit tests.
- **Zero Leakage to Generator**: The LLM prompt context contains solely authorized chunks, eliminating the risk of LLMs ignoring post-generation filtering instructions.

### Negative / Trade-offs
- Connection poolers (e.g., PgBouncer in transaction pooling mode) require session state to be reset per transaction via `SET LOCAL` or connection checkout hooks. We implement explicit session management in our async SQLAlchemy engine layer.
