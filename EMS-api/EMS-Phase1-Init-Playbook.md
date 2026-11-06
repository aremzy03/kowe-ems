# EMS Phase 1 — Coding Agent Prompt Playbook

**Purpose:** Completes IAM/RBAC (role permissions, staff provisioning, parent self-signup + linking codes, 2FA for admin/bursar) and builds the core academic structure (Session, Term, ClassLevel, Subject, Student, Guardian, Enrollment). Assumes the Phase 0 playbook has already been run and verified: multi-tenant foundation, shared `User` model, JWT auth with cookie-based refresh, and a working local test tenant.

Run in order. Verify each prompt's output before moving to the next.

---

## Primer — paste this once at the start of the session

```
Continuing the multi-tenant K-12 EMS project. Phase 0 is complete: django-tenants
is configured, schema-per-tenant with subdomain resolution works, shared `accounts.User`
model exists, JWT auth (SimpleJWT, httpOnly cookie refresh) is wired up, and a
`memberships.SchoolMembership` model exists (tenant-scoped: FK to User, role
choices admin/teacher/bursar/parent).

This phase builds:
1. RBAC permission classes based on SchoolMembership.role
2. Staff account provisioning (admin/teacher/bursar) via admin invite — NOT
   self-signup, that's parent-only per the PRD
3. Parent self-signup with school-issued linking-code verification before any
   student data becomes visible
4. Mandatory 2FA for admin and bursar roles
5. Core academic structure: Session, Term, ClassLevel, Arm, Subject, Student,
   Guardian, Enrollment — all tenant-scoped, in the `academics` app

Follow existing project conventions: UUID primary keys, DRF serializers/viewsets,
migrations written incrementally. After each prompt, summarize what was built
and flag any assumption you made that wasn't explicit in these instructions.
```

---

## Prompt 1 — RBAC permission classes

```
Build tenant-aware, role-aware DRF permission classes in the `memberships` app.

1. A base `HasActiveMembership` permission: confirms request.user has an active
   SchoolMembership in the currently resolved tenant schema (not just that
   they're authenticated — an authenticated user from another tenant's context
   should not pass).
2. Role-specific permission classes built on top of it: IsSchoolAdmin,
   IsTeacher, IsBursar, IsParent, and a composable IsAdminOrBursar for
   endpoints both roles need (e.g., viewing financial summaries).
3. A helper to attach the resolved SchoolMembership to the request object
   (request.membership) during permission checking, so viewsets don't need to
   re-query it.
4. Write these so queryset filtering later (e.g., "teacher only sees their own
   classes") can compose with request.membership rather than duplicating role
   lookups in every viewset.

Do not build any endpoints yet — this prompt is permission infrastructure only.
Show me the permission classes and a short example of how a viewset would use
one.
```

---

## Prompt 2 — Staff account provisioning (admin/teacher/bursar)

```
Staff accounts (admin, teacher, bursar) are NOT self-signup — only parent
accounts are (per PRD decision). Staff are provisioned by invitation. Note:
I'm assuming the FIRST admin account per school is created by the platform
admin during tenant onboarding (extend the create_test_tenant-style flow from
Phase 0 to also create an initial SchoolMembership with role=admin for a
given email) — flag if you think this assumption needs revisiting.

Build:
1. A `StaffInvite` model (tenant-scoped, in `memberships`): email, role
   (teacher/bursar/admin), invited_by (FK to User), token (unique, expiring),
   status (pending/accepted/expired), created_at.
2. Endpoint: IsSchoolAdmin-only, POST to create an invite for an email + role.
   Sends an email (use Django's email backend, console backend for local dev)
   with a link containing the invite token, pointed at the tenant's subdomain.
3. Endpoint: public (no auth) — accept-invite. Given a valid, non-expired
   token: if a User with that email doesn't exist, create one (they set a
   password here); if a User already exists (e.g., a teacher at a second
   school), just create the new SchoolMembership for this tenant. Mark the
   invite accepted.
4. Handle the case where the token is expired or already used — clear error
   response, not a silent failure.

Show me the invite creation and acceptance flow end-to-end, including what the
email content looks like for local dev (console backend output).
```

---

## Prompt 3 — Mandatory 2FA for admin and bursar

```
Add TOTP-based two-factor authentication, required for admin and bursar roles.

1. Add django-otp (or another TOTP library — pick one, justify briefly) to
   dependencies. This is identity-related, so the OTP device model should live
   in the shared/public schema tied to the User model, not per-tenant — a
   user's 2FA device shouldn't need re-enrollment per school they belong to.
2. Enrollment endpoint: authenticated user requests a TOTP secret + QR code
   (for an authenticator app), confirms enrollment by submitting a valid code
   once.
3. Modify the login flow from Phase 0: after password authentication succeeds,
   check request.membership role (once tenant/role context is known — this may
   require restructuring login slightly since role is tenant-scoped and login
   happens against the shared User). If the resolved membership role is admin
   or bursar, require a valid TOTP code as a second step before issuing
   tokens. If the role is teacher/parent, tokens issue immediately after
   password.
4. Enforce at the permission-class level too, not just at login: if an
   admin/bursar user somehow has a valid session without a confirmed 2FA
   device, block access to admin/bursar-scoped endpoints with a clear error
   directing them to complete 2FA enrollment. Don't rely on login-time
   enforcement alone.

This prompt has real design ambiguity around how tenant-scoped role
determines a shared-schema login flow — walk me through your approach before
writing code, since this is the trickiest interaction in the whole phase.
```

---

## Prompt 4 — Parent self-signup + linking code redemption

```
1. Public self-signup endpoint: creates a User (email + password, no invite
   needed) and a SchoolMembership with role=parent for the current tenant
   (resolved from subdomain). At this point the parent has an account but is
   linked to zero students — no student data should be queryable yet.
2. `StudentLinkingCode` model (tenant-scoped, in `academics` — reserve the
   model here even though full Student/Guardian models come in Prompt 5):
   code (unique, e.g., 8-char alphanumeric), student (FK, nullable until
   Prompt 5 defines Student), is_used, used_by (FK to User, nullable),
   used_at, created_at.
3. Redeem-code endpoint: authenticated parent submits a code. If valid and
   unused, create a link between the parent User and the student (the actual
   Guardian-Student relationship model comes in Prompt 5 — for now, stub the
   linking logic with a clear TODO if Student doesn't exist yet, OR build
   Prompt 4 and 5 together if that's cleaner — your call, tell me which you
   chose and why), mark the code used.
4. A parent's access to ANY student-scoped endpoint (results, attendance, fees
   — built in later phases) must check that an active, redeemed link exists
   between that parent and that specific student. Build this as a reusable
   permission/filter now even though the endpoints it protects don't exist
   yet, so later phases don't have to retrofit it.

Confirm: after signup and before redeeming any code, hitting a
student-data-shaped endpoint (even a placeholder one) returns no data and no
information leakage about which students exist.
```

---

## Prompt 5 — Academic structure models

```
Build the `academics` app's core models (tenant-scoped):

- Session: name (e.g., "2026/2027"), start_date, end_date, is_active
- Term: session (FK), name (1st/2nd/3rd), start_date, end_date, is_active
- ClassLevel: name (e.g., "JSS1", "SS2")
- Arm: class_level (FK), name (e.g., "A", "B")
- Subject: name, code
- Student: first_name, last_name, date_of_birth, gender, admission_number
  (unique per tenant), admission_date
- Guardian: linked to a parent User (FK), relationship_to_student
  (mother/father/guardian), phone_number
- StudentGuardianLink: student (FK), guardian (FK), is_primary_contact —
  this is the actual relationship created when a linking code is redeemed
  (connect this to Prompt 4's StudentLinkingCode.student FK now)
- Enrollment: student (FK), class_level (FK), arm (FK), session (FK),
  term (FK), enrolled_at, status (active/withdrawn/graduated)

Wire StudentLinkingCode.student to the real Student model now. Add a
model method or manager on Student for "generate a new unused linking code"
— call this automatically when a Student is created during enrollment
(admin/teacher-facing, built in Prompt 6).

Run makemigrations and migrate_schemas --tenant against your local test
tenant. Confirm all tables exist correctly scoped to that tenant's schema —
verify by checking a second test tenant's schema does NOT have this data.
```

---

## Prompt 6 — Admin-facing CRUD for academic structure

```
Build DRF viewsets + serializers for admin-only management of:
Session, Term, ClassLevel, Arm, Subject, Student (with automatic guardian
linking-code generation on creation), Enrollment.

- All endpoints IsSchoolAdmin-permission gated except read-only views of
  ClassLevel/Arm/Subject which teachers should also be able to list (they
  need this to select their class when entering marks later).
- Student creation endpoint should, in one request, accept student details +
  optionally an initial Guardian's name/phone (without requiring the parent
  User to exist yet — the guardian record can exist ahead of the parent
  actually signing up and redeeming the code), and return the generated
  linking code in the response so the admin can hand it to the parent.
- Enrollment creation: student + class_level + arm + session + term.
  Validate the student isn't already actively enrolled in the same
  session/term.

Show me the full endpoint list with HTTP methods and required roles.
```

---

## Prompt 7 — Bruno collection updates

```
Extend the existing Bruno collection with requests covering this phase's
new flows, organized by folder:

- Auth: staff invite creation, invite acceptance, 2FA enrollment, 2FA login
  step
- Parents: self-signup, linking code redemption, verify no data leakage
  before redemption
- Academics: full CRUD sequence for Session → Term → ClassLevel → Arm →
  Subject → Student (capture linking code from response) → Enrollment

Include a chained environment variable setup (access token, refresh cookie,
linking code) so the sequence can run end-to-end without manual copy-paste
between requests, matching the pattern from incel-hrm/incel-esign.
```

---

## After completing this phase

Verify before moving to Phase 2 (CA & grading engine):

- [ ] A teacher/bursar/admin account can only be created via invite, never
      self-signup
- [ ] A parent can sign up freely but sees zero student data until a code is
      redeemed
- [ ] Admin/bursar accounts cannot access protected endpoints without
      completing 2FA enrollment
- [ ] Two test tenants' academic structures are fully isolated from each
      other
- [ ] The full Bruno sequence (staff invite → parent signup → student
      creation → code redemption → enrollment) runs cleanly end-to-end
