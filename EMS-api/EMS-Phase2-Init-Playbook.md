# EMS Phase 2 — Coding Agent Prompt Playbook

**Purpose:** Builds the highest-priority MVP module — configurable weighted continuous assessment, score entry, term-average computation with class ranking, teacher broadsheet view, grade-change audit logging, and WeasyPrint report card PDF generation. Assumes Phase 0 (multi-tenant foundation) and Phase 1 (RBAC, staff/parent flows, 2FA, academic structure: Session/Term/ClassLevel/Arm/Subject/Student/Guardian/Enrollment) are complete and verified.

Run in order. This phase is the core value proposition for the pilot school — verify each prompt's correctness carefully, since a wrong average or a leaked grade is the kind of bug that destroys trust with a real school fast.

---

## Primer — paste this once at the start of the session

```
Continuing the multi-tenant K-12 EMS. Phases 0-1 are complete: multi-tenant
foundation with django-tenants, RBAC permission classes based on
SchoolMembership.role, staff invite flow, parent self-signup with linking-code
gated student access, mandatory 2FA for admin/bursar, and the academics app
(Session, Term, ClassLevel, Arm, Subject, Student, Guardian,
StudentGuardianLink, Enrollment, StudentLinkingCode).

This phase builds the `assessment` app: configurable weighted CA components,
score entry (with idempotent upsert for offline-resilience per the PRD),
term-average computation with class ranking, teacher broadsheet views, grade-
change audit logging, and report card PDF generation via WeasyPrint.

Continue existing conventions: UUID primary keys, tenant-scoped models unless
stated otherwise, DRF serializers/viewsets, incremental migrations. Flag
assumptions after each prompt.
```

---

## Prompt 1 — Class-subject-teacher assignment

```
Before building assessment, we need to know which teacher teaches which
subject to which class/arm — this wasn't built in Phase 1.

Build `ClassSubjectAssignment` (tenant-scoped, in `academics`): teacher (FK to
User, must have an active teacher SchoolMembership — validate this), subject
(FK), class_level (FK), arm (FK), term (FK).

1. Admin-only CRUD endpoints for managing assignments.
2. A read-only endpoint for the currently authenticated teacher: "my
   assignments" — returns only their own class/subject/term assignments.
   This becomes the foundation for scoping every teacher-facing endpoint in
   the rest of this phase — a teacher should never be able to enter or view
   marks for a class/subject they aren't assigned to.
3. Build a reusable permission/filter helper (similar pattern to Phase 1's
   HasActiveMembership) that other viewsets in this phase will use to
   restrict teacher access to only their assigned class/subject/term
   combinations.

Show me this helper — it gets reused in Prompts 3 and 5.
```

---

## Prompt 2 — Configurable weighted assessment components

```
Build `AssessmentComponent` (tenant-scoped, in `assessment`): subject (FK),
class_level (FK), term (FK), name (e.g., "1st CA", "2nd CA", "Exam"),
weight_percentage (decimal), max_score (decimal, e.g., 100).

1. Validation: for a given subject + class_level + term combination, the sum
   of weight_percentage across all its components must equal 100. Enforce
   this at the serializer/model level, not just in the frontend — reject
   invalid configurations before they can be saved.
2. Admin-only CRUD endpoints. Include an endpoint to clone a component scheme
   from one subject/class to another (or from a previous term) — schools
   will want to reuse the same 1st CA/2nd CA/Exam structure across
   subjects rather than configuring 3 components × N subjects by hand every
   term.
3. A read endpoint scoped to teachers: given their ClassSubjectAssignment,
   return the components they need to enter marks against.

Confirm the 100% validation rejects a bad configuration with a clear error
message, and show me the clone-scheme endpoint working.
```

---

## Prompt 3 — Score entry with idempotent upsert

```
Build `Score` (tenant-scoped, in `assessment`): student (FK), assessment_component
(FK), score (decimal), entered_by (FK to User), updated_at.

Unique constraint on (student, assessment_component) — this is what makes the
entry idempotent: submitting the same student+component twice updates, never
duplicates.

1. Validation: score cannot exceed assessment_component.max_score. Reject
   with a clear error, don't silently clamp.
2. Permission: only the teacher assigned (via ClassSubjectAssignment) to that
   subject/class/term can enter or edit scores for it — reuse Prompt 1's
   helper. Admin can also enter/override any score.
3. Build a BULK upsert endpoint: teacher submits an array of
   {student_id, assessment_component_id, score} for an entire class at once.
   Each entry in the array upserts independently (by the unique constraint) —
   if the request is retried after a dropped connection (per the PRD's
   offline-mitigation approach), re-submitting the same payload must be safe
   and produce the same end state, not duplicate or double-count anything.
   Return per-entry success/failure in the response so a partial failure
   (e.g., one student's score exceeds max) doesn't silently discard the
   valid entries in the same batch.
4. Audit logging: on any Score create/update, write to an `AuditLog` model
   (tenant-scoped, in `assessment` or a shared `core` app — your call, tell
   me which and why) capturing: student, assessment_component, old_value,
   new_value, changed_by, timestamp. This must be automatic (signal-based),
   not something the teacher-facing endpoint has to remember to call.

Test the bulk endpoint's idempotency explicitly: submit the same batch twice,
confirm no duplicate Score rows and the AuditLog only reflects an actual
change on the second submission, not a no-op update logged as a change.
```

---

## Prompt 4 — Term-average computation & class ranking

```
Computing rank requires comparing every student in a class, so this needs a
materialized result, not just an on-the-fly per-student calculation.

Build `TermResult` (tenant-scoped, in `assessment`): student (FK), subject
(FK), term (FK), computed_score (decimal — the weighted sum across that
subject's components), computed_at.

Also build `TermResultSummary` (tenant-scoped): student (FK), term (FK),
overall_average (decimal, across all subjects), class_position (integer,
rank within their class_level+arm+term), teacher_remark (text, nullable),
admin_remark (text, nullable).

1. A service function (not a signal on every Score save — that would recompute
   constantly during bulk entry) that recomputes TermResult for a given
   student+subject+term from their current Scores × component weights.
2. A separate service/management command to recompute TermResultSummary for
   an entire class+term: pulls all students' TermResults, computes each
   student's overall_average, then ranks all students in that class/arm/term
   to set class_position for everyone at once (ranking requires the full
   set, not one student in isolation).
3. Admin/teacher-facing endpoint: "recompute results for this class+term" —
   explicit trigger rather than automatic on every score change, since
   recomputing ranks on every single mark entry during active bulk entry
   would be wasteful. Document this tradeoff clearly for me.
4. Read endpoint: given a student+term, return their TermResultSummary +
   per-subject TermResult breakdown — this is what the broadsheet and report
   card will consume.

Explain your recomputation trigger strategy (manual trigger vs. periodic
Celery task vs. something else) and why, since this affects when a teacher
sees "stale" vs. current class rankings.
```

---

## Prompt 5 — Teacher broadsheet view

```
Build a read-only broadsheet endpoint: given a class_level + arm + term
(and implicitly, only the teacher's assigned subject, or all subjects if
requested by admin), return a grid of student × assessment-component scores
plus the computed term total per subject.

1. Teacher-scoped: only their assigned subject/class/term, using Prompt 1's
   permission helper.
2. Admin-scoped: full broadsheet across all subjects for a class+term.
3. Shape the response so the frontend can render it as a table without
   further client-side computation — rows = students, columns = components +
   computed subject total.

Show me an example response payload for a small class (3-4 students, 3
components) so I can confirm the shape is usable directly by a frontend
table component.
```

---

## Prompt 6 — Report card PDF generation (WeasyPrint)

```
1. Add WeasyPrint to dependencies. Update the Dockerfile to install the
   required system packages (Pango, Cairo, GDK-PixBuf, and any other
   WeasyPrint runtime deps for the base image you're using — check current
   WeasyPrint docs for the exact package list, this varies by base image).
2. Build an HTML template for the report card: school name/logo placeholder,
   student info, per-subject scores (from TermResult) with component
   breakdown, overall_average, class_position (from TermResultSummary),
   teacher_remark, admin_remark. Leave a clearly marked placeholder section
   for attendance summary — attendance module isn't built until Phase 3, so
   this section should render gracefully as empty/"Not available" rather
   than error if attendance data doesn't exist yet.
3. Endpoint: generate report card PDF for a given student+term.
   - Parent: only their linked student(s) (enforce via Phase 1's linking
     verification)
   - Teacher: only students in their assigned classes
   - Admin: any student in the tenant
4. Return the PDF as a downloadable response, not inline HTML.
5. Add a remarks-editing endpoint (teacher can set teacher_remark on
   TermResultSummary for their students; admin can set admin_remark for
   anyone) — this needs to exist before report card generation is useful,
   since the template renders these fields.

Generate a sample PDF for a test student with a full set of scores and
confirm it renders correctly (share what the generated PDF looks like or
confirm it opens without error).
```

---

## Prompt 7 — Bruno collection updates

```
Extend the Bruno collection with a new folder for this phase covering the
full teacher workflow end-to-end:

1. Admin creates ClassSubjectAssignment for a teacher
2. Admin configures AssessmentComponent scheme for a subject (verify the
   100% validation rejects a bad config, then submit a valid one)
3. Teacher bulk-submits scores for their class
4. Re-submit the SAME bulk payload again — confirm no duplication (idempotency
   check)
5. Trigger result/ranking recomputation for the class+term
6. Fetch broadsheet as teacher (own subject only) and as admin (full)
7. Set teacher_remark and admin_remark
8. Generate report card PDF as parent (only their linked child), teacher
   (only their students), and admin (any student) — confirm role boundaries
   are enforced, not just that the happy path works
```

---

## After completing this phase

Verify before moving to Phase 3 (attendance):

- [ ] AssessmentComponent weights are rejected if they don't sum to 100
- [ ] Bulk score submission is genuinely idempotent — retry produces no
      duplicates and no false audit-log entries
- [ ] A teacher cannot enter or view scores for a class/subject they aren't
      assigned to
- [ ] Class ranking is correct and only recomputes on explicit trigger, not
      on every score save
- [ ] A parent can only generate a report card for their linked child(ren),
      never any other student
- [ ] Generated PDF renders correctly with real WeasyPrint output, not just
      passes without erroring
