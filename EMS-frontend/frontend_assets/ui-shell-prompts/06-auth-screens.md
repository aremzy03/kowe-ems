# 06 — Auth Screens (Mock)

**Goal:** Auth UI flows with mock handlers only.

**Acceptance:** Can “log in” as each role from `/login`; admin/bursar path shows 2FA mock; parent signup + link-student screens exist.

### Agent prompt

```
Build EMS auth screens under app/(auth) using UI primitives. All submit handlers are mocks — set mock session and router.push to the role home. No real API.

Screens:
1. /login — neo-brutalism dial UP. Email + password. Role quick-pick for demo (“Continue as Admin/Teacher/Bursar/Parent/Platform”) OR password submit that maps demo emails to roles. Link to parent signup. Note: “Admins and bursars complete 2FA next.”
2. /2fa/verify — 6-digit inputs, Verify → set session for admin/bursar
3. /2fa/enroll — QR placeholder + manual key mono + confirm code (mock success)
4. /invite/accept — name, password, role Badge from query ?role=teacher
5. /parents/signup — parent registration form → mock login as parent → /parent
6. /link-student — redeem linking code input (mono), success adds a mock child

Use Card, Button primary yellow, calm body text. Nigerian copy (Test Academy). After mock login redirect:
- admin → /admin
- teacher → /teacher
- bursar → /bursar
- parent → /parent
- platform_admin → /platform
```
