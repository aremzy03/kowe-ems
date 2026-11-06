# 02 — UI Primitives

**Goal:** Shared neo-brutalist components used by all screens.

**Acceptance:** Story-less but each primitive exported from `components/ui/*` and demoed on a `/dev/ui` page.

### Agent prompt

```
Build EMS UI primitives under components/ui using Tailwind + our CSS tokens. Neo-brutalism interaction physics:
- hover: translate -2px/-2px + stronger hard shadow
- active: translate into shadow, shadow-none
- focus-visible: outline 3px #ffde4d, outline-offset 3px (outside shadow)

Create:
1. Button — variants: primary (yellow #ffde4d), secondary (white), inverted (black), destructive, ghost. Sizes sm/md/lg.
2. Card — white, 3px border, hard shadow; optional accentTop: primary|accent|warning|destructive
3. Input, Label, Textarea, Select — dial DOWN shadows (small)
4. Badge — variants with label text: default, success/cyan, warning/yellow, danger/red, info/blue
5. Table wrappers — Table, THead, TBody, TR, TH, TD (2px borders, muted header)
6. Modal/Dialog — thick border feel, large hard shadow, dimmed backdrop
7. EmptyState — headline, body, primary+secondary actions
8. PageHeader — title, description, actions slot
9. KpiCard — label, big number (Space Grotesk), mono delta, accentTop

Add app/dev/ui/page.tsx showcasing all primitives with Nigerian sample copy.

No forms library required yet. Accessible: button types, label association, dialog focus trap if using Radix — Radix/shadcn OK if restyled to our tokens (override rounded-full and soft shadows).
```
