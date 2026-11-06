# EMS Phase 4 — Coding Agent Prompt Playbook

**Purpose:** Builds fee structures, invoicing, Paystack subaccount-based payment routing (each school gets paid directly, your platform takes a commission automatically), manual payment recording, and the multi-tenant webhook handling this requires. This is where the payment architecture discussed earlier actually gets implemented. Assumes Phases 0-3 are complete and verified.

**Before starting:** your project has a `paystack-integration` skill covering standard transaction initialize/verify/webhook patterns for Django/DRF — reference it for the base implementation (`references/django-drf.md`). It does **not** cover subaccounts specifically, since that's the multi-tenant-specific piece this phase builds — the agent should pull current Paystack API docs for the Subaccount and bank-resolution endpoints rather than guessing at request/response shapes.

---



## Primer — paste this once at the start of the session

```
Continuing the multi-tenant K-12 EMS. Phases 0-3 are complete: multi-tenant
foundation, RBAC/staff/parent flows, 2FA, academic structure, the CA/grading
engine with report cards, and the attendance module.

This phase builds the `finance` app (tenant-scoped) plus a small amount of
shared/public-schema infrastructure for cross-tenant payment routing.

Architecture recap: ONE platform-level Paystack account (mine). Each school
gets a Paystack Subaccount, created via API using verified bank details.
Payments split automatically at Paystack's end — the school's share settles
directly to their bank account, my commission stays with the platform
account. The Django app never holds or moves school funds directly; Paystack
does the routing. Only my platform secret key is ever used — no per-school
secrets are stored anywhere.

Continue existing conventions. Flag assumptions after each prompt.
```

---



## Prompt 1 — School payment account onboarding

```
Build `SchoolPaymentAccount` (tenant-scoped, in `finance`): gateway (choices,
'paystack' for now), subaccount_code, bank_name, bank_code, account_number,
account_name, platform_commission_pct (decimal), is_verified (bool),
is_active (bool), created_at.

1. Admin-only endpoint: submit bank_code + account_number (+ commission
   percentage, or read this from a platform-wide default setting — your
   call, tell me which).
2. Server-side call to Paystack's account resolution endpoint (GET
   /bank/resolve) to confirm the account name matches before proceeding —
   this is a fraud/typo guardrail, do not skip it. Store the resolved
   account_name, don't trust the admin's manually-typed name.
3. Server-side call to Paystack's Create Subaccount endpoint (POST
   /subaccount) using the resolved bank details and platform secret key.
   Store the returned subaccount_code. Mark is_verified and is_active true
   only after this succeeds.
4. Mask account_number in any serializer output (last 4 digits only) — full
   number stored for gateway calls, never displayed in full via the API.
5. Block online fee payment initialization (built in Prompt 3) for any school
   without an active, verified SchoolPaymentAccount — fall back to manual
   payment recording only (Prompt 5) until this is set up.

Show me the resolve → create-subaccount → store flow end-to-end against
Paystack's test environment.
```

---



## Prompt 2 — Fee structures and invoicing

```
Build (tenant-scoped, in `finance`):

- FeeStructure: class_level (FK), term (FK), name (e.g., "Tuition", "PTA
  Levy", "Sports Fee"), amount (decimal).
- Invoice: student (FK), term (FK), total_amount (decimal, sum of applicable
  FeeStructure items for the student's class_level+term), status (choices:
  unpaid, partially_paid, paid), created_at.
- InvoiceLineItem: invoice (FK), fee_structure (FK), amount (decimal) —
  itemized breakdown so a parent can see what they're being charged for,
  not just a lump sum.

1. Admin-only CRUD for FeeStructure.
2. Endpoint (admin/bursar): generate invoices for an entire class+term at
   once — pulls applicable FeeStructure items for each enrolled student,
   creates Invoice + InvoiceLineItems. Handle the case where invoices
   already exist for some students in that class+term (skip, don't
   duplicate).
3. Parent-facing read endpoint: their linked student's invoices, itemized,
   with current payment status.

Show me the invoice generation endpoint handling a class of several students
at once, confirming no duplicate invoices on a re-run.
```

---



## Prompt 3 — Payment initialization (subaccount split)

```
Build `Payment` (tenant-scoped, in `finance`): invoice (FK), amount (decimal),
reference (unique), status (choices: pending, success, failed), gateway
('paystack'), paid_at (nullable), created_at.

1. Endpoint: parent initiates payment for an invoice (full or partial amount
   — confirm with me whether partial payment is in scope for MVP or full-
   invoice-only is simpler; PRD doesn't specify, use your judgment and flag
   it).
2. Server-side call to Paystack's Initialize Transaction endpoint, passing:
   amount (in kobo — do not forget this conversion), email (parent's),
   subaccount: the school's subaccount_code from Prompt 1, and a reference
   that encodes enough to trace back to (tenant, invoice) later — note that
   Paystack references must be alphanumeric plus -._= only, so if you encode
   tenant/invoice info directly in the reference, sanitize accordingly, or
   alternatively just generate a random reference and store the
   tenant/invoice mapping in your own Payment row (simpler — recommend this
   approach and explain why).
3. Return the checkout authorization_url to the frontend. Do NOT mark
   anything paid at this point — that only happens after server-side
   verification (Prompt 4) or webhook confirmation (Prompt 5), never on the
   frontend's redirect alone.
4. Block this endpoint if the school has no active SchoolPaymentAccount
   (from Prompt 1).

Confirm the amount-to-kobo conversion is correct and show me the full
initialize-transaction request payload being sent to Paystack.
```

---



## Prompt 4 — Server-side verification endpoint

```
Build a verification endpoint the frontend calls after the user returns from
Paystack's checkout (in addition to, not instead of, the webhook in Prompt 5
— webhooks can be delayed or missed, so having both a return-flow check and
a webhook is the reliable pattern).

1. Given a payment reference, call Paystack's Verify Transaction endpoint
   server-side.
2. Confirm the returned amount matches what was expected for that Payment
   record — a customer could in theory tamper with client-side state, so
   don't trust anything except what Paystack's verify response says.
3. If verified successful and not already processed (check Payment.status
   isn't already 'success' — idempotent, since this might be called
   alongside the webhook for the same transaction): mark Payment success,
   update the related Invoice's status (unpaid → partially_paid or paid
   based on cumulative payments against it).
4. This endpoint's logic (verify + apply payment) should be extracted into a
   shared service function, since Prompt 5's webhook handler needs to do the
   exact same thing — don't duplicate this logic in two places.

Show me the shared service function signature and how both this endpoint and
the upcoming webhook handler will call it.
```

---



## Prompt 5 — Multi-tenant webhook handling

```
This is the trickiest part of the phase. Paystack sends webhooks to ONE
global endpoint on the platform domain — not a school subdomain — so
django-tenants' normal subdomain-based schema resolution does not apply
here. The handler has to resolve the tenant manually.

1. Build a SHARED/public-schema model: `SubaccountTenantMap` — subaccount_code,
   tenant (FK to platform_admin.Tenant). Populate this automatically whenever
   Prompt 1's subaccount creation succeeds (write to this shared table at the
   same time the tenant-scoped SchoolPaymentAccount is created).
2. Single webhook endpoint at the platform domain level (not tenant-routed),
   CSRF-exempt (standard for webhooks), reading the RAW request body (not
   parsed JSON) for signature verification — refer to the paystack-
   integration skill's webhook security section for the exact HMAC-SHA512
   verification pattern, and confirm you're using `request.body` (raw
   bytes) not an already-parsed body.
3. After signature verification passes: extract the subaccount code from the
   event payload, look up the tenant via SubaccountTenantMap (this lookup
   happens in the public schema, before entering any tenant context).
4. Use django-tenants' `schema_context(tenant.schema_name)` to enter that
   specific tenant's schema, then call the SAME shared service function from
   Prompt 4 to verify + apply the payment — reuse, don't duplicate.
5. Idempotency: enforce a unique constraint on Payment.reference (already
   in place from Prompt 3) so if this webhook fires more than once for the
   same transaction (Paystack does retry undelivered webhooks), the second
   call is a safe no-op, not a double-credit.
6. Return HTTP 200 immediately after acknowledging receipt — if any part of
   this processing could be slow, offload to Celery and return 200 first,
   per the paystack-integration skill's guidance on this.
7. Log every webhook received (even ones that fail signature verification or
   can't be matched to a tenant) to a shared-schema `WebhookLog` model for
   debugging — a payment that silently fails to route because of a bug here
   could mean a school never gets notified of a real payment.

Explain the exact order of operations (signature check → subaccount lookup →
schema_context entry → service call) and confirm none of these steps can be
reordered in a way that would process an unverified or misrouted payload.
```

---



## Prompt 6 — Manual payment recording (bursar)

```
Not every parent will pay online. Build a bursar-facing endpoint to manually
record a payment (cash, bank transfer) against an invoice: invoice, amount,
method (choices: cash, bank_transfer), recorded_by (FK), notes.

1. This creates a Payment record directly with status='success' (no gateway
   verification needed — the bursar is asserting the money was received) but
   gateway='manual', distinct from Paystack-originated payments.
2. Same invoice-status update logic as Prompt 4/5 — reuse the shared service
   function where possible rather than duplicating the "update invoice
   status based on cumulative payments" logic a third time.
3. Admin/bursar-only permission.
```

---



## Prompt 7 — Platform revenue tracking and collection dashboard

```
1. Build `PlatformTransactionLog` in the SHARED/public schema: tenant (FK),
   payment_reference, gross_amount, commission_amount, net_to_school,
   timestamp. Write to this at the same point Prompt 5's webhook (or Prompt
   4's verification endpoint) successfully processes a Paystack payment —
   manual payments (Prompt 6) don't generate platform commission, so those
   don't write here.
2. Platform-admin-only endpoint (you, not school staff): revenue overview
   across all tenants — total commission earned, broken down by school and
   time period. This is what makes your platform-wide revenue visible
   without iterating every tenant schema individually. 
3. School-facing (admin/bursar) collection dashboard: outstanding balance
   total, collection rate (paid vs. invoiced) for the current term, broken
   down by class.
```

---



## Prompt 8 — Bruno collection updates

```
Extend the Bruno collection with a folder for this phase, using Paystack's
test-mode bank account (Bank 057 / Zenith Bank, Account 0000000000) and test
cards from the paystack-integration skill:

1. Admin submits bank details → resolve → subaccount creation
2. Admin generates invoices for a class
3. Parent initializes payment for an invoice → complete via test card →
   server-side verification endpoint confirms
4. Simulate the SAME webhook event being delivered twice (Paystack does
   retry) — confirm no double-crediting
5. Bursar manually records a cash payment
6. Fetch collection dashboard as admin, invoice list as parent (own child
   only)
7. Send a malformed/unsigned webhook payload — confirm it's rejected and
   logged, not silently processed
```

---



## After completing this phase

Verify before moving to Phase 5 (notifications):

- [ ] No secret key exists anywhere except the single platform-level
  ```
  PAYSTACK_SECRET_KEY environment variable
  ```
- [ ] Account resolution runs before every subaccount creation — no
  ```
  unverified bank details get a subaccount
  ```
- [ ] A payment is never marked successful based on frontend redirect alone
- [ ] Webhook signature verification happens before any payload data is
  ```
  trusted or processed
  ```
- [ ] The same transaction processed via both the verification endpoint AND
  ```
  a webhook retry does not result in double-crediting
  ```
- [ ] A malformed or unsigned webhook is logged and rejected, not silently
  ```
  dropped or processed
  ```
- [ ] Platform commission tracking in PlatformTransactionLog matches what
  ```
  Paystack's dashboard shows for the same transactions
  ```

