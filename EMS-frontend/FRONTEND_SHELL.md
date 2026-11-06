# EMS Frontend Shell

Mock-data UI shell for the Education Management System (Next.js App Router).  
**No live Django API wiring yet** — that follows in [`frontend_assets/api-integration-prompts/`](frontend_assets/api-integration-prompts/) (or the sibling API handoff prompts).

## Design authority — Paper Brutalism

Source of truth: [`DESIGN.md`](DESIGN.md) (not the older neo-brutalism blue/yellow notes in some prompt README snippets).

| Token | Value | Role |
|---|---|---|
| Ink | `#211F26` | Borders, text |
| Paper | `#FBF6EC` | Page background |
| Paper card | `#FFFFFB` | Surfaces |
| Accent-1 | `#5B3DE8` | Primary CTA / brand |
| Accent-2 | `#FF7A45` | Secondary / fee-due emphasis |

**Rules for this shell:**

- No primary-blue chrome, no yellow CTAs.
- JetBrains Mono for all `₦` amounts (via `Money` / `formatNaira`).
- Intensity **DOWN** near money (bursar, parent pay confirmation); **MEDIUM** on parent home; **DOWN–MEDIUM** on platform.
- Trustworthy finance UI — no playful illustrations on fee/payment pages.
- Status always color + label (never color alone).

## Stack

- Next.js 15 App Router + TypeScript + Tailwind CSS v4
- Path alias `@/`
- Mock session cookie (`EMS_MOCK_ROLE`) + role middleware
- Mock modules under `src/lib/mocks/`

## Route map

### Auth (`(auth)`)

| Route | Purpose |
|---|---|
| `/login` | Role picker / mock login |
| `/2fa/setup`, `/2fa/enroll`, `/2fa/verify` | 2FA flows |
| `/invite/accept` | Staff invite |
| `/parents/signup` | Parent signup |
| `/link-student` | Linking code redeem |

### Staff — Admin / Teacher / Bursar (`(staff)` + `StaffShell`)

| Route | Purpose |
|---|---|
| `/admin` | Dashboard KPIs + needs attention |
| `/admin/academics` | Sessions, terms, levels/arms, subjects |
| `/admin/students` | Student table + linking codes |
| `/admin/enrollment` | Enroll / unenroll dual list |
| `/admin/staff` | Members + invites |
| `/admin/assignments` | Subject + form teachers |
| `/admin/attendance` | Class submission overview |
| `/admin/fees` | Read-only collections by class |
| `/teacher` | Assignments + form-teacher home |
| `/teacher/marks` | Dense mark entry (+ localStorage draft) |
| `/teacher/components` | Assessment weight validation |
| `/teacher/attendance` | Daily register P/L/A |
| `/teacher/broadsheet` | Class × subject grid |
| `/teacher/remarks` | Remarks + report-card preview |
| `/bursar` | Collections KPIs + recent payments |
| `/bursar/fee-structures` | Structures table + create/edit panel |
| `/bursar/invoices` | Filterable list + detail drawer |
| `/bursar/invoices/generate` | 3-step generate wizard (mock) |
| `/bursar/payments` | Payment history |
| `/bursar/payments/manual` | Manual Cash/Transfer form |
| `/bursar/payment-account` | Bank fields, masked account, Verified |

### Parent (`(parent)` + `ParentShell`)

| Route | Purpose |
|---|---|
| `/parent` | Child snapshots + Pay now |
| `/parent/students` | Linked children + empty state |
| `/parent/results` | Average, position, subjects, PDF toast |
| `/parent/attendance` | P/L/A calendar + term summary |
| `/parent/fees` | Invoice cards |
| `/parent/fees/pay` | Confirm before mock Paystack |
| `/parent/fees/result?status=success\|failed` | Result panels |
| `/parent/more` | Account + shortcuts |

### Platform (`(platform)` + `PlatformShell` top nav)

| Route | Purpose |
|---|---|
| `/platform` | Revenue KPIs + per-tenant table |
| `/platform/tenants` | Schools / schema / subdomain |
| `/platform/webhooks` | Log table + detail drawer |

## Mock modules

| File | Contents |
|---|---|
| `src/lib/mocks/session.ts` | Mock users, roles, cookie helpers |
| `src/lib/mocks/session-client.tsx` | Client session provider |
| `src/lib/mocks/staff-nav.ts` | Admin / teacher / bursar nav |
| `src/lib/mocks/admin.ts` | Dashboard, academics, students, staff, fees |
| `src/lib/mocks/teacher.ts` | Marks, components, broadsheet, attendance, remarks |
| `src/lib/mocks/bursar.ts` | Collections, structures, invoices, payments, account |
| `src/lib/mocks/parent.ts` | Children store + results / attendance / fees |
| `src/lib/mocks/platform.ts` | Revenue, tenants, webhooks |

Shared UI helpers: `src/lib/format-money.ts`, `src/components/ui/money.tsx`, `src/components/ui/toast.tsx`.

## Next step

Wire screens to the Django API using **api-integration-prompts** (TanStack Query / real `fetch`, auth cookies, tenant host). Keep Paper Brutalism tokens; replace mock modules incrementally without changing route shapes where possible.
