# EMS — UI Shell Prompts (Frontend Agent)

Prompts for a **Cursor / coding agent** to scaffold the Next.js App Router frontend: design system, app shells, and **mock-data screens**. No live API wiring here — that lives in [`../api-integration-prompts/`](../api-integration-prompts/).

## Design source of truth

Copy tokens from the API repo handoff files into the new Next app:

| File | Use |
|---|---|
| `frontend_assets/index.css` | CSS variables + Tailwind v4 `@theme` |
| `frontend_assets/layout.tsx` | Space Grotesk + JetBrains Mono root layout pattern |

**Brand:** paper `#f7f9f1`, primary `#0e4bcd`, accent `#00f0ff`, CTA/focus `#ffde4d`, ink `#000000`, hard shadow `5px 4px 0`, radius `4px`, neo-brutalism.

## How to run these prompts

1. Open (or create) the **Next.js frontend repo** (sibling to `EMS-api` is fine).
2. Paste prompts **in order** (`00` → `11`) into the agent. Finish each phase before the next.
3. Each file has a **`### Agent prompt`** block — paste that. Human notes above explain scope and acceptance.
4. Prefer **one prompt per agent turn**. Do not skip to API integration until the shell passes acceptance checks.

## Stack targets

- Next.js 15 App Router
- TypeScript
- Tailwind CSS v4
- Path alias `@/`
- Mock data modules under `src/mocks/` (or `lib/mocks/`)
- No TanStack Query / real `fetch` to Django yet (stub hooks OK if they read mocks)

## Suggested route map (mock)

```
app/
  (auth)/login, 2fa/*, invite/accept, parents/signup, link-student
  (staff)/layout.tsx          ← sidebar shell
    admin/...
    teacher/...
    bursar/...
  (parent)/layout.tsx         ← bottom-tab / simpler shell
    ...
  (platform)/...
```

Role routing can be fake (query `?role=` or mock session cookie) until API integration.

## Prompt index

| # | File | Deliverable |
|---|---|---|
| 00 | `00-design-system.md` | Tokens + intensity rules |
| 01 | `01-bootstrap-nextjs.md` | Create/configure Next app |
| 02 | `02-ui-primitives.md` | Button, Card, Input, Badge, Table, Toast |
| 03 | `03-app-router-structure.md` | Route groups, layouts, mock session |
| 04 | `04-staff-shell.md` | Sidebar + top bar |
| 05 | `05-parent-shell.md` | Parent chrome |
| 06 | `06-auth-screens.md` | Auth UI with mocks |
| 07 | `07-admin-screens.md` | Admin pages + mock data |
| 08 | `08-teacher-screens.md` | Teacher pages + mocks |
| 09 | `09-bursar-screens.md` | Bursar pages + mocks |
| 10 | `10-parent-screens.md` | Parent pages + mocks |
| 11 | `11-platform-screens.md` | Platform admin pages + mocks |

## Neo-brutalism intensity

| Surface | Dial |
|---|---|
| Auth, empty states, primary CTAs | UP |
| Dashboards / KPI cards | MEDIUM |
| Tables, mark entry, attendance, fees | DOWN |

## After shell is done

Hand off to [`../api-integration-prompts/`](../api-integration-prompts/).
