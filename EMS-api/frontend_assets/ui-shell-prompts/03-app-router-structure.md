# 03 — App Router Structure + Mock Session

**Goal:** Route groups and a fake auth/session so shells can branch by role without the API.

**Acceptance:** Visiting `/admin`, `/teacher`, `/bursar`, `/parent`, `/platform` renders the correct group layout; unauthenticated mock redirects to `/login`.

### Agent prompt

```
Set up Next.js App Router structure for EMS with mock auth (no Django yet).

Route groups:
- app/(auth)/… — login, 2fa, invite accept, parent signup, link-student (no chrome)
- app/(staff)/admin/…, teacher/…, bursar/… — shared staff layout later
- app/(parent)/… — parent layout later
- app/(platform)/… — platform layout later

Mock session:
- lib/mocks/session.ts exporting MockUser { id, email, name, role: 'admin'|'teacher'|'bursar'|'parent'|'platform_admin', schoolName }
- Simple client provider or cookie `ems_mock_role` set from /login mock buttons
- middleware.ts (or client guard components) that sends users without mock session to /login, and blocks wrong-role paths with a /403 page

Create placeholder page.tsx under each role home:
- /admin — “Admin dashboard (mock)”
- /teacher — “Teacher home (mock)”
- /bursar — “Bursar dashboard (mock)”
- /parent — “Parent home (mock)”
- /platform — “Platform revenue (mock)”

Also /403 error page using EmptyState-style neo-brutalist card.

Keep implementations minimal — shells come in prompts 04–05. Use realistic Test Academy copy.
```
