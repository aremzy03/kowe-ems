# 10 — Parent Screens (Mock Data)

**Goal:** Parent portal pages for linked children.

**Acceptance:** Child switcher drives results/attendance/fees; empty state when no children; pay flow is UI-only.

### Agent prompt

```
Implement Parent pages under app/(parent) with lib/mocks/parent.ts.

Pages:
1. /parent — Home: ChildSwitcher, snapshots for results / attendance / fee balance, Pay now CTA
2. /parent/students — list + Link another child → /link-student; empty state if none
3. /parent/results — average, position, subject rows, Download PDF button (toast)
4. /parent/attendance — month list/calendar cells with P/L/A labels+colors; term summary
5. /parent/fees — invoice cards with status badges; Pay → /parent/fees/pay
6. /parent/fees/pay — confirmation before “Paystack” (mock redirect to result)
7. /parent/fees/result?status=success|failed — success/fail panels

Mobile-first. Dial MEDIUM overall; DOWN on pay confirmation.
```
