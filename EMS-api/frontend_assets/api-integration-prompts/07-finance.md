# 07 — Finance Integration

**Goal:** Bursar ops + parent pay via Paystack initialize/verify.

### Agent prompt

```
Wire finance UI to /api/finance/ via tenant-scoped apiFetch (prompt 01: single API host + X-Tenant-Slug). Dial DOWN UI; focus correctness. Do not call a school-subdomain API host.

lib/api/finance.ts:
- payment-account/ GET/PUT (or as views define)
- fee-structures ViewSet
- invoices/generate/ POST
- my-invoices/ GET (parent)
- payments/initialize/ POST → authorization_url / reference for Paystack redirect
- payments/verify/ POST after return URL
- payments/manual/ POST (bursar)
- dashboard/collections/ GET

Bursar pages: replace mocks with queries/mutations. Manual payment form posts payments/manual/.

Parent pay flow:
1. my-invoices list
2. initialize payment
3. redirect to Paystack URL
4. return route calls verify then shows success/fail

Do not implement Paystack webhook in Next — that stays on Django at the single API host (`/api/webhooks/paystack/`). Tenant for webhooks is resolved server-side from Paystack payload, not from X-Tenant-Slug or frontend Host.

Use Decimal/string amounts carefully; format ₦ in UI only. Never trust client-only paid status — always verify via API.
```
