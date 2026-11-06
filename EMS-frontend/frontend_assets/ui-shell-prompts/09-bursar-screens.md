# 09 — Bursar Screens (Mock Data)

**Goal:** Fee ops UI — trustworthy, dial DOWN near money.

**Acceptance:** Collections dashboard + fee structures + invoices + manual payment modal + payment account form, all mock-backed.

### Agent prompt

```
Implement Bursar pages under app/(staff)/bursar with lib/mocks/bursar.ts.

Pages:
1. /bursar — Collections dashboard: KPI ₦ cards, recent payments table, CTAs Record manual payment / Generate invoices
2. /bursar/fee-structures — table + create/edit panel with line items and live total ₦
3. /bursar/invoices — filterable list + detail drawer (line items, payment history)
4. /bursar/invoices/generate — 3-step wizard UI (scope → preview → confirm) mock only
5. /bursar/payments/manual — form/modal: student/invoice search, amount, method Cash|Transfer, reference, date
6. /bursar/payment-account — bank fields, masked account, Verified badge

Finance trust rules: no playful empty illustrations on money pages; yellow CTA sparingly; JetBrains Mono for all ₦.
```
