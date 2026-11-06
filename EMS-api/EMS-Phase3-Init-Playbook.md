# EMS Phase 3 — Coding Agent Prompt Playbook

**Purpose:** Builds daily attendance registers and termly attendance summaries, feeding into the report card's previously-placeholder attendance section from Phase 2. Assumes Phases 0-2 are complete and verified: multi-tenant foundation, RBAC/staff/parent flows, 2FA, academic structure, and the CA/grading engine with report card generation.

This is a smaller module than Phase 2, but it surfaces one real design gap worth resolving carefully in Prompt 1.

---

## Primer — paste this once at the start of the session

```
Continuing the multi-tenant K-12 EMS. Phases 0-2 are complete: multi-tenant
foundation, RBAC, staff invite + parent self-signup with linking-code
verification, 2FA for admin/bursar, academic structure (Session, Term,
ClassLevel, Arm, Subject, Student, Guardian, Enrollment,
ClassSubjectAssignment), and the assessment app (weighted CA components,
idempotent bulk score entry, TermResult/TermResultSummary with class ranking,
broadsheet, audit logging, WeasyPrint report cards with a placeholder
attendance section).

This phase builds the `attendance` app: daily registers and termly summaries,
then wires the real data into the report card's attendance section.

Continue existing conventions. Flag assumptions after each prompt.
```

---

## Prompt 1 — Class teacher assignment (attendance-taking authority)

```
Attendance is taken once per day for a whole class/arm — it's not
subject-specific the way Phase 2's ClassSubjectAssignment is. A school
typically has one "form teacher" or "class teacher" responsible for the daily
register, which may or may not be the same person as any of that class's
subject teachers.

Build `ClassTeacherAssignment` (tenant-scoped, in `academics` or `attendance`
— your call, tell me why): teacher (FK to User, must have active teacher
SchoolMembership), class_level (FK), arm (FK), term (FK).

1. Admin-only CRUD.
2. Read endpoint for a teacher: "my class(es)" — the class/arm/term
   combinations where they're the assigned class teacher, distinct from
   Phase 2's "my subject assignments."
3. Permission helper (matching the pattern from Phase 2's Prompt 1): only the
   assigned class teacher for a given class/arm/term (or admin) can mark or
   edit attendance for it.

A teacher could be both a subject teacher AND a class teacher for the same or
different classes — don't assume these are mutually exclusive or automatically
linked.
```

---

## Prompt 2 — Daily attendance entry

```
Build `DailyAttendance` (tenant-scoped, in `attendance`): student (FK),
class_level (FK), arm (FK), term (FK), date, status (choices: present,
absent, late, excused), marked_by (FK to User), remarks (text, optional).

Unique constraint on (student, date) — one attendance record per student per
day, regardless of how many subjects they have that day.

1. Bulk entry endpoint, same idempotency pattern as Phase 2's score entry:
   class teacher submits an array of {student_id, status, remarks} for a
   given class/arm/date. Upsert by the (student, date) unique constraint —
   retrying the same submission after a dropped connection must not create
   duplicates or produce a different result.
2. Permission: only that class/arm/term's assigned class teacher, or admin,
   using Prompt 1's helper.
3. Audit logging on attendance changes (e.g., a student marked absent then
   corrected to present later that day): reuse the AuditLog pattern from
   Phase 2. If Phase 2's AuditLog currently lives inside the `assessment`
   app, this is a good signal to move it into a shared `core` app now that
   two modules need it — make that call and tell me what you did and why.

Test idempotency explicitly the same way Phase 2 did: submit the same batch
twice, confirm no duplicate records and no false audit entries on the
no-op resubmission.
```

---

## Prompt 3 — Termly attendance summary

```
Unlike Phase 2's class ranking, a student's attendance percentage doesn't
depend on comparing against other students — it's a pure per-student
aggregate (days present / total school days that term). This means it COULD
be computed on-the-fly from DailyAttendance records rather than materialized.

Decide between:
(a) Compute on read — a service function that aggregates DailyAttendance
    for a student+term whenever requested (report card generation, parent
    view)
(b) Materialize into an AttendanceSummary model, recomputed on an explicit
    trigger or incrementally as records are entered

Make the call based on expected query frequency (report cards get generated
per student per term — not a high-frequency read) and tell me your reasoning.
Whichever you choose, also handle: what counts as a "total school day" for
the denominator — this needs a concept of school calendar/term working days,
which doesn't exist yet. Propose the simplest reasonable approach (e.g., a
Term.total_school_days field the admin sets manually per term) rather than
building a full academic calendar module — that's out of scope for MVP.

Build the read endpoint(s): a student's termly attendance summary, and a
class-wide register view (grid: student × date, for a given month or term) for
teachers/admins.
```

---

## Prompt 4 — Wire attendance into report card generation

```
Go back to Phase 2's report card PDF template and replace the placeholder
attendance section with real data: total school days, days present, days
absent, days late, attendance percentage — sourced from Prompt 3's summary
approach.

If a student has zero attendance records for the term (e.g., attendance
module wasn't in use yet, or student just enrolled), render this gracefully
("Attendance data not available") rather than showing zeros that would
misrepresent the student as having been absent every day.

Regenerate a sample report card PDF for a test student with real attendance
data and confirm the section renders correctly.
```

---

## Prompt 5 — Parent and admin read access

```
1. Parent-facing endpoint: view their linked student's daily attendance log
   and termly summary — read-only, same linking-verification enforcement as
   Phase 2's report card access.
2. Admin-facing endpoint: attendance overview across the whole school for a
   given date or term — this feeds the admin dashboard's "pending mark-entry
   status" style visibility mentioned in the PRD (e.g., which classes haven't
   had attendance marked for today).
```

---

## Prompt 6 — Bruno collection updates

```
Extend the Bruno collection with a folder for this phase:

1. Admin creates ClassTeacherAssignment
2. Class teacher bulk-submits attendance for their class on a given date
3. Re-submit the SAME batch — confirm idempotency (no duplicates, no false
   audit entries)
4. Attempt attendance submission as a teacher NOT assigned as class teacher
   for that class — confirm it's rejected
5. Fetch termly attendance summary as parent (own child only), teacher (own
   class), and admin (any student)
6. Generate a report card PDF and confirm the attendance section now shows
   real data instead of the Phase 2 placeholder
```

---

## After completing this phase

Verify before moving to Phase 4 (fee management + Paystack):

- [ ] Only the assigned class teacher (or admin) can mark attendance for a
      given class/arm/date
- [ ] Bulk attendance submission is idempotent under retry
- [ ] Attendance percentage calculation is correct and the "total school
      days" concept is explicit, not silently assumed
- [ ] Report cards show real attendance data, with graceful handling when
      no records exist yet
- [ ] A parent cannot view attendance for any student other than their
      linked child(ren)
