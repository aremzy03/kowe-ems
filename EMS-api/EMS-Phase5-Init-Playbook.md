# EMS Phase 5 — Coding Agent Prompt Playbook

**Purpose:** Builds the minimal omnichannel communication layer — email and WhatsApp notifications triggered by invoice generation, payment confirmation, and term result publication. Assumes Phases 0-4 are complete and verified. This phase also closes a small gap left open in Phase 2: there's currently no explicit "publish" step for results, meaning a parent-facing results endpoint (if built naively) could expose grades before the school intends to release them.

**Before starting:** your project has a `whatsapp-integration` skill covering the WhatsApp Business Cloud API. One constraint from it matters a lot here: **outbound notifications sent proactively (not in reply to a user's message within the last 24 hours) require pre-approved Meta message templates** — free-form text won't work for invoice/payment/result notifications since the school is always initiating contact, not replying. Template approval has real lead time (minutes to hours per the skill, but budget more for a first-time WABA setup) — this is worth starting **before** you need it working end-to-end, not something to leave until the last prompt.

---

## Primer — paste this once at the start of the session

```
Continuing the multi-tenant K-12 EMS. Phases 0-4 are complete: multi-tenant
foundation, RBAC/staff/parent flows, 2FA, academic structure, the CA/grading
engine with report cards, attendance, and fee management with Paystack
subaccount-based payment routing.

This phase builds the `communications` app (tenant-scoped): async email and
WhatsApp notifications for three triggers — invoice generated, payment
confirmed, term result published. It also adds an explicit "publish" step to
Phase 2's TermResultSummary, since results currently become queryable as soon
as they're computed, with no school-controlled release gate.

Continue existing conventions. Notification sending must be async (Celery),
never inline in the request-response cycle that creates the invoice/payment/
result — a slow or failed WhatsApp API call must not block or fail the
underlying business operation. Flag assumptions after each prompt.
```

---

## Prompt 1 — NotificationLog model and Celery wiring

```
Build `NotificationLog` (tenant-scoped, in `communications`): recipient (FK
to User), channel (choices: email, whatsapp), trigger_type (choices:
invoice_generated, payment_confirmed, result_published), status (choices:
queued, sent, failed), related_object_id (generic — invoice/payment/
result-summary id, for traceability), error_message (nullable), sent_at
(nullable), created_at.

1. Confirm Celery + Redis is wired up from Phase 0's docker-compose (worker
   service) — if not fully configured yet, complete that setup now.
2. Build the base async task pattern: a Celery task that takes a
   NotificationLog id, attempts to send via the appropriate channel (email
   or whatsapp service, built in Prompts 2-3), and updates status +
   error_message based on outcome. Don't build the actual sending logic in
   this prompt — just the task/logging skeleton.
3. Retry policy: on transient failure (network error, rate limit), retry
   with exponential backoff (max 3 attempts). On permanent failure (invalid
   phone number, template rejected), mark failed immediately, don't retry.

Show me the task signature and retry configuration.
```

---

## Prompt 2 — Email notification service

```
1. Configure Django's email backend: console backend for local dev, and
   settings scaffolding for a real SMTP/transactional email provider in
   production (read credentials from environment variables — don't pick a
   specific provider unless I've told you which one; use Django's generic
   SMTP backend config as the production placeholder).
2. Build an `EmailNotificationService` with three template-driven methods:
   send_invoice_generated, send_payment_confirmed, send_result_published.
   Each takes the relevant object (Invoice, Payment, TermResultSummary) and
   the recipient, renders an HTML email template, and sends it — wrapped in
   the Celery task from Prompt 1, not called synchronously.
3. Simple HTML email templates for each of the three triggers — parent-
   facing tone, include the relevant summary info (amount due, amount paid,
   or a note that results are available) and a link to the frontend (don't
   embed sensitive data like full scores in the email body itself — link to
   the portal, since email isn't a secure channel).

Show me one full example: invoice-generated email, rendered with test data.
```

---

## Prompt 3 — WhatsApp notification service

```
Per the whatsapp-integration skill's Option B pattern (service class,
queue-based sending), build a `WhatsAppNotificationService`.

1. Phone number resolution: pull from Guardian.phone_number (built in Phase
   1). Validate/normalize to E.164 format before sending — if a guardian's
   number is missing or malformed, log the notification as failed with a
   clear error_message rather than throwing an unhandled exception that
   could affect other queued notifications.
2. This requires three pre-approved Utility-category templates (per the
   skill's guidance — proactive notifications outside the 24h window need
   templates, free-form text will fail): one each for invoice_generated,
   payment_confirmed, result_published. Draft the template content/variable
   placeholders here even though actual Meta approval is a manual dashboard
   step outside this codebase — I'll need to submit these for approval
   separately, so make the placeholders clear and give me the exact text to
   submit.
3. Wire sending through the Celery task from Prompt 1, using the skill's
   documented rate limits (pair limit: 1 message per user per 6 seconds) —
   if you're sending to an entire class at once (e.g., bulk result
   publication), make sure the task queue naturally throttles rather than
   firing all messages simultaneously and hitting the pair-limit error
   (code 131056).

Show me the three template drafts (with variable placeholders) I need to
submit for Meta approval, and confirm the queue throttling approach for
bulk sends.
```

---

## Prompt 4 — Add explicit result publication gate (retrofit to Phase 2)

```
This closes a gap: Phase 2's TermResultSummary becomes queryable as soon as
it's computed, with no school-controlled release step — meaning a parent
could see results before the school intends to release them, if the
parent-facing read endpoint doesn't already gate on something.

1. Add is_published (bool, default False) and published_at (nullable
   datetime) to TermResultSummary.
2. Update the parent-facing report card / results endpoints from Phase 2 to
   only return data where is_published is True. Admin/teacher views remain
   unaffected — they should see results regardless of publish status, since
   they're the ones deciding when to publish.
3. Build an admin-only "publish results" endpoint: given a class_level + arm
   + term, sets is_published=True and published_at=now() for every
   TermResultSummary in that group, and triggers the result_published
   notification (Prompt 1's NotificationLog + Celery task) for each
   affected student's linked parent(s).

Confirm: before this prompt, could a parent already see unpublished
results through any existing endpoint? Audit Phase 2's endpoints and tell
me honestly if this was already a live gap, not just a theoretical one.
```

---

## Prompt 5 — Wire remaining triggers via signals

```
Wire the other two triggers using Django signals, so notification dispatch
doesn't need to be manually called from every place an invoice or payment
could be created:

1. invoice_generated: signal on Invoice creation (Phase 4). Note Phase 4's
   bulk invoice generation endpoint creates many invoices at once — trigger
   one notification per invoice, not one bulk notification, so each parent
   gets their own itemized message.
2. payment_confirmed: signal (or direct call, if cleaner given Phase 4's
   shared verify/apply service function) triggered when a Payment's status
   transitions to 'success' — this must fire for Paystack-verified payments
   AND manually-recorded bursar payments (Phase 4 Prompt 6), not just one
   path.
3. For both, create the NotificationLog entries for BOTH channels (email +
   whatsapp) if the guardian has a phone number, or email-only if they
   don't — don't fail the whole notification attempt just because one
   channel is unavailable.

Confirm signal receivers are idempotent — if an Invoice or Payment record is
updated in a way that re-triggers the signal without a real state change
(e.g., an unrelated field edit), it shouldn't re-send a notification.
```

---

## Prompt 6 — Admin visibility into notification delivery

```
Build an admin-facing endpoint: list NotificationLog entries with filtering
by status/trigger_type/date range, so a school admin (or you, debugging)
can see whether notifications are actually being delivered — this matters
because a silent WhatsApp template rejection or a bad phone number
shouldn't be something you only discover when a parent complains they never
got a fee reminder.

Include a manual "resend" action for failed notifications (admin-triggered,
re-queues the same NotificationLog via Celery).
```

---

## Prompt 7 — Bruno collection updates

```
Extend the Bruon collection [sic — Bruno] with a folder for this phase:

1. Generate invoices for a class → confirm NotificationLog entries created
   for each parent, both channels where applicable
2. Record a manual payment → confirm payment_confirmed notification queued
3. Attempt to fetch results as parent BEFORE publishing → confirm empty/
   blocked response
4. Admin publishes results for a class → confirm results now visible to
   parent AND result_published notifications queued
5. Fetch NotificationLog as admin, filter by failed status, trigger a resend
```

---

## After completing this phase

Verify before considering the MVP feature-complete:

- [ ] No notification sending happens synchronously inside a request that
      creates an invoice, payment, or published result — all async via
      Celery
- [ ] A parent cannot see term results before an admin explicitly publishes
      them — confirmed by testing the gap directly, not just trusting the
      code
- [ ] A missing or invalid guardian phone number degrades to email-only,
      doesn't break the whole notification flow
- [ ] WhatsApp templates are drafted and submitted for Meta approval (this
      has a real external lead time — don't let it block other work, but
      don't forget it either)
- [ ] Bulk notification sends (e.g., publishing results for a full class)
      respect WhatsApp's pair rate limit rather than firing all at once
- [ ] Admin can see delivery status and manually resend failed
      notifications
