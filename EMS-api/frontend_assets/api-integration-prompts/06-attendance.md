# 06 — Attendance Integration

**Goal:** Form-teacher register, parent daily/summary, admin overview.

### Agent prompt

```
Wire attendance UI to /api/attendance/ via tenant-scoped apiFetch (prompt 01: single API host + X-Tenant-Slug). Do not introduce a per-school API base URL.

lib/api/attendance.ts:
- GET/POST register/ for class daily register (inspect Bruno Attendance for payload shape — bulk upsert)
- daily ViewSet as needed
- summaries/student/
- parents/daily/
- admin/overview/
- audit-logs read-only if shown

Teacher attendance page: load my-classes, select date, fetch register, toggle Present/Late/Absent, save bulk.

Parent attendance: parents/daily + summaries/student for selected child.

Admin attendance overview: admin/overview/.

Preserve idempotent save semantics (retries safe). Keep toggle labels+colors for a11y.
```
