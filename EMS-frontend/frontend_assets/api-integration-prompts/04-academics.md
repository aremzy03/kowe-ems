# 04 — Academics Integration

**Goal:** Admin academics + students + enrollment + assignments; parent linking; teacher my-assignments/my-classes.

### Agent prompt

```
Wire academics UI to /api/academics/ via tenant-scoped apiFetch from prompt 01 (single API host + X-Tenant-Slug). Do not call a school-subdomain API host.

Use ViewSet conventions (list/create/retrieve/update/partial_update/destroy) as exposed by DRF routers.

lib/api/academics.ts + TanStack Query hooks:
- sessions, terms, class-levels, arms, subjects
- students, enrollments
- class-subject-assignments, class-teacher-assignments
- redeemLinkingCode → POST linking-codes/redeem/
- myStudents → GET my-students/ (+ detail)
- myAssignments → GET my-assignments/
- myClasses → GET my-classes/

Replace admin academics/students/enrollment/staff-assignment pages’ mock loaders with these queries/mutations. Optimistic UI optional; prefer invalidateQueries on success.

Parent: link-student page calls redeem; my-students feeds ChildSwitcher. Linking-code pages live on the school frontend subdomain so the tenant header is already set.

Teacher home: cards from my-assignments + my-classes.

Types: generate manually from Bruno examples or infer from serializers — keep UUID strings as string. Handle pagination if API returns paginated results.

Do not touch assessment/attendance/finance in this prompt.
```
