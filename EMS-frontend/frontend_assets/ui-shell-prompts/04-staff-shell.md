# 04 — Staff App Shell

**Goal:** Desktop sidebar + top bar for admin/teacher/bursar.

**Acceptance:** Staff routes share one layout; nav items differ by mock role; active route highlighted cyan.

### Agent prompt

```
Implement the EMS staff app shell for (staff) route group.

Layout (desktop-first, 1440):
1. Left sidebar ~260px, bg sidebar token #dce2ca, 3px black right border.
   - Brand “EMS” bold + school name from mock session (“Test Academy”)
   - Nav links depend on role:
     - admin: Dashboard, Academics, Students, Staff, Attendance, Fees
     - teacher: Home, Mark entry, Attendance, Broadsheet
     - bursar: Dashboard, Fee structures, Invoices, Payments, Payment account
   - Active item: bg accent #00f0ff, text black, bold
   - Footer: user name, role Badge, Log out (clears mock session → /login)
2. Top bar: white, 3px bottom border, page title slot, session/term mono pill “2025/2026 · First Term”
3. Main: bg background #f7f9f1, padding, children

Components: components/layout/StaffSidebar.tsx, StaffTopbar.tsx, StaffShell.tsx.
Wire app/(staff)/layout.tsx to StaffShell.

Mobile: collapse sidebar to a bordered drawer triggered by menu button (keep neo-brutalist, not a soft Material drawer).

Do not build page contents yet beyond existing placeholders.
```
