"""
Paystack webhook — single API host (see config.urls).

This is the one money path that is NOT tenant-header-routed. The order of
operations below is a security invariant and must not be reordered:

  1. Read raw ``request.body`` bytes.
  2. Read ``X-Paystack-Signature``.
  3. Verify HMAC-SHA512 of those raw bytes. Fail closed.
  4. If HMAC fails: log (public schema) and return 401. Do not parse JSON,
     do not read reference/subaccount/amount/metadata, do not look up a
     tenant, do not enter a tenant schema, do not apply a payment.
  5. Only after HMAC OK: parse JSON from the same raw bytes.
  6. If the event is not ``charge.success``: log and return 200 (ack).
  7. Extract subaccount code from the verified payload.
  8. Resolve tenant via SubaccountTenantMap in the PUBLIC schema
     (before any tenant schema context).
  9. Unknown / missing subaccount: log and return 400. Do not apply.
 10. Enter ``schema_context(tenant.schema_name)``.
 11. Call ``verify_and_apply_payment(reference)`` — the SAME function the
     Prompt 4 return-flow endpoint uses. Do not copy verify / amount-match
     / SUCCESS / invoice-recompute here.
 12. Log the outcome on the public schema and return 200 (idempotent
     retries of the same reference are a safe no-op inside that function).

CSRF-exempt: Paystack cannot send a CSRF token. Auth is the HMAC, not a
session. Processing is inline (one Paystack verify HTTP + DB writes) then
200; there is no Celery app in this project yet.
"""

import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_tenants.utils import get_public_schema_name, schema_context

from finance.paystack import verify_webhook_signature
from finance.services import verify_and_apply_payment
from platform_admin.models import SubaccountTenantMap, WebhookLog

logger = logging.getLogger(__name__)

_PAYLOAD_LOG_LIMIT = 16384


def _clip(raw_body):
    if not raw_body:
        return ''
    if isinstance(raw_body, (bytes, bytearray)):
        text = bytes(raw_body).decode('utf-8', errors='replace')
    else:
        text = str(raw_body)
    if len(text) > _PAYLOAD_LOG_LIMIT:
        return text[:_PAYLOAD_LOG_LIMIT] + '…'
    return text


def _subaccount_code(data):
    """Pull Paystack subaccount_code from verified charge data. Never from Host."""
    sub = data.get('subaccount')
    if isinstance(sub, dict):
        return (sub.get('subaccount_code') or '').strip()
    if isinstance(sub, str):
        return sub.strip()
    return ''


def _resolve_tenant(subaccount_code):
    """
    Public-schema lookup. Must run BEFORE entering any tenant schema.

    Returns the Tenant or None. Inactive tenants are treated as unmapped
    so we never credit a disabled school.
    """
    if not subaccount_code:
        return None
    with schema_context(get_public_schema_name()):
        mapping = (
            SubaccountTenantMap.objects.select_related('tenant')
            .filter(subaccount_code=subaccount_code)
            .first()
        )
        if mapping is None:
            return None
        tenant = mapping.tenant
        if not tenant.is_active:
            return None
        return tenant


def _log_webhook(
    *,
    signature_valid,
    outcome,
    event='',
    reference='',
    subaccount_code='',
    tenant=None,
    error_message='',
    raw_body=b'',
):
    try:
        WebhookLog.record(
            signature_valid=signature_valid,
            outcome=outcome,
            event=event or '',
            reference=reference or '',
            subaccount_code=subaccount_code or '',
            tenant_id=tenant.pk if tenant is not None else None,
            error_message=error_message or '',
            payload=_clip(raw_body),
        )
    except Exception:
        logger.exception('Failed to persist WebhookLog (outcome=%s)', outcome)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    # --- 1. Raw bytes. Nothing in the payload is trusted yet. ---
    raw_body = request.body
    # --- 2. Signature header (empty string if missing). ---
    signature = request.headers.get('X-Paystack-Signature') or ''
    # --- 3. HMAC-SHA512 of the raw bytes. Fail closed. ---
    if not verify_webhook_signature(raw_body, signature):
        # --- 4. Reject BEFORE json.loads / tenant lookup / apply. ---
        _log_webhook(
            signature_valid=False,
            outcome=WebhookLog.Outcome.SIGNATURE_INVALID,
            raw_body=raw_body,
        )
        return HttpResponse(status=401)

    # --- 5. Signature OK: parse the SAME bytes that were verified. ---
    try:
        event = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        _log_webhook(
            signature_valid=True,
            outcome=WebhookLog.Outcome.INVALID_JSON,
            raw_body=raw_body,
        )
        return HttpResponse(status=400)

    if not isinstance(event, dict):
        _log_webhook(
            signature_valid=True,
            outcome=WebhookLog.Outcome.INVALID_JSON,
            raw_body=raw_body,
        )
        return HttpResponse(status=400)

    event_type = event.get('event') or ''
    data = event.get('data') if isinstance(event.get('data'), dict) else {}
    reference = str(data.get('reference') or '')
    subaccount_code = _subaccount_code(data)

    # --- 6. Ack events we do not apply. Do not enter a tenant schema. ---
    if event_type != 'charge.success':
        _log_webhook(
            signature_valid=True,
            outcome=WebhookLog.Outcome.IGNORED_EVENT,
            event=event_type,
            reference=reference,
            subaccount_code=subaccount_code,
            raw_body=raw_body,
        )
        return HttpResponse(status=200)

    # --- 7–8. Tenant from public map, keyed by subaccount code. ---
    # Host header is irrelevant; the map is the only routing source.
    tenant = _resolve_tenant(subaccount_code)
    if tenant is None:
        # --- 9. Unknown / missing subaccount: do not apply. ---
        _log_webhook(
            signature_valid=True,
            outcome=WebhookLog.Outcome.UNKNOWN_SUBACCOUNT,
            event=event_type,
            reference=reference,
            subaccount_code=subaccount_code,
            raw_body=raw_body,
        )
        return HttpResponse(status=400)

    if not reference:
        _log_webhook(
            signature_valid=True,
            outcome=WebhookLog.Outcome.MISSING_REFERENCE,
            event=event_type,
            subaccount_code=subaccount_code,
            tenant=tenant,
            raw_body=raw_body,
        )
        return HttpResponse(status=400)

    # --- 10–11. Enter THAT tenant's schema, then the shared apply function. ---
    try:
        with schema_context(tenant.schema_name):
            verify_and_apply_payment(reference)
    except Exception as exc:
        logger.exception(
            'Paystack webhook apply failed reference=%s schema=%s',
            reference,
            tenant.schema_name,
        )
        _log_webhook(
            signature_valid=True,
            outcome=WebhookLog.Outcome.ERROR,
            event=event_type,
            reference=reference,
            subaccount_code=subaccount_code,
            tenant=tenant,
            error_message=str(exc),
            raw_body=raw_body,
        )
        return HttpResponse(status=500)

    # --- 12. Ack. Duplicate deliveries of the same reference are idempotent. ---
    _log_webhook(
        signature_valid=True,
        outcome=WebhookLog.Outcome.APPLIED,
        event=event_type,
        reference=reference,
        subaccount_code=subaccount_code,
        tenant=tenant,
        raw_body=raw_body,
    )
    return HttpResponse(status=200)
