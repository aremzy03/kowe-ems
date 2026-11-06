.# 05 — Assessment Integration

**Goal:** Components, idempotent score upsert, recompute, broadsheet, remarks, report PDF.

### Agent prompt

```
Wire teacher/admin assessment UI to /api/assessment/ via tenant-scoped apiFetch (prompt 01: single API host + X-Tenant-Slug). Do not introduce a per-school API base URL.

lib/api/assessment.ts:
- components CRUD via /components/
- my-components/
- scores list/create/update — treat upsert as idempotent (student+component); match Bruno Assessment bulk/idempotency behavior
- results/recompute/ POST
- results/student/ GET
- results/remarks/ POST/PATCH as API defines
- broadsheet/ GET
- report-cards/ GET blob PDF (responseType arrayBuffer/blob) → download link

Mark entry page: load roster from academics enrollment/students for class; load components; save scores via mutation; show toast on success; keep localStorage draft as offline mitigation until save succeeds.

Broadsheet + remarks pages: real data; PDF button downloads WeasyPrint file.

Respect RBAC errors (403) with existing error UI. Dial DOWN UI unchanged.
```
