# 07 — Admin Screens (Mock Data)

**Goal:** Admin IA filled with mocks — look production-ready, data is static.

**Acceptance:** All admin nav routes render; tables/KPIs read from `lib/mocks/admin.ts`.

### Agent prompt

```
Implement School Admin pages under app/(staff)/admin with mock data modules. Dial neo-brutalism MEDIUM on dashboard, DOWN on tables.

Pages + routes:
1. /admin — Dashboard: 4 KpiCards (students, fee collection %, attendance today, pending mark entry); “Needs attention” list; simple collections chart optional (CSS bars OK)
2. /admin/academics — tabs Sessions/Terms, Class levels & Arms, Subjects — CRUD-looking forms that only update local mock state
3. /admin/students — searchable table (admission mono, name, class); Add student modal; row action “Linking code” modal showing mono LINK-****
4. /admin/enrollment — dual list not-enrolled / enrolled for JSS 1A mock
5. /admin/staff — members table + pending invites; Invite modal (email + role)
6. /admin/assignments — subject teachers + form teachers tables
7. /admin/attendance — overview KPIs + class submission table
8. /admin/fees — read-only collection overview KPIs + by-class table (bursar owns ops)

Mock file: lib/mocks/admin.ts with Nigerian names, ₦ amounts, JSS/SSS classes, 2025/2026 session.
Wire StaffSidebar admin links to these routes. No fetch().
```
