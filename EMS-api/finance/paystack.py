"""
Thin Paystack API client for the finance app.

Only the single platform-level PAYSTACK_SECRET_KEY is ever used — schools
never have their own keys. Each function returns the ``data`` dict from
Paystack's response envelope, or raises PaystackError with a caller-safe
message.

Kobo conversion happens ONLY here (the gateway boundary). Domain amounts
are always Decimal naira.

Webhook signature verification lives here and MUST run on the raw request
bytes (`request.body`) before any JSON parse or field is trusted.
"""

import hashlib
import hmac
import logging
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = 'https://api.paystack.co'
_TIMEOUT_SECONDS = 30

# Local Bruno / HMAC-fixture only. Never on in production (DEBUG is False).
STUB_SUBACCOUNT_CODE = 'ACCT_bruno_local_stub'
STUB_ACCOUNT_NAME = 'PAYSTACK TEST ACCOUNT'


def gateway_stub_enabled():
    """
    True only when DEBUG and PAYSTACK_STUB_GATEWAY.

    Lets Prompt 8 prove webhook HMAC + double-delivery against the local
    endpoint when ``PAYSTACK_SECRET_KEY`` is not a live ``sk_test_``.
    Production cannot enable this: ``DEBUG`` is False there even if the
    env flag is set.
    """
    if not getattr(settings, 'DEBUG', False):
        return False
    return bool(getattr(settings, 'PAYSTACK_STUB_GATEWAY', False))


class PaystackError(Exception):
    """A Paystack call failed. ``message`` is safe to surface to API clients."""

    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _headers():
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError('Payment gateway is not configured on this platform.')
    return {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def _request(method, path, *, params=None, json=None):
    try:
        response = requests.request(
            method,
            f'{PAYSTACK_BASE_URL}{path}',
            params=params,
            json=json,
            headers=_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        logger.exception('Paystack request failed: %s %s', method, path)
        raise PaystackError('Payment gateway is unreachable. Try again later.')

    try:
        body = response.json()
    except ValueError:
        body = {}

    if not response.ok or not body.get('status'):
        # Paystack returns e.g. 422 with a helpful message when an account
        # number cannot be resolved. Surface that message, never the payload.
        message = body.get('message') or 'Payment gateway request failed.'
        logger.warning(
            'Paystack %s %s -> HTTP %s: %s', method, path, response.status_code, message
        )
        raise PaystackError(message, status_code=response.status_code)

    return body.get('data') or {}


def resolve_bank_account(account_number, bank_code):
    """
    GET /bank/resolve — confirm the account exists and get its registered name.

    Returns {'account_number': ..., 'account_name': ..., 'bank_id': ...}.
    """
    if gateway_stub_enabled():
        logger.warning(
            'PAYSTACK_STUB_GATEWAY: skipping live GET /bank/resolve '
            '(account=%s bank=%s)',
            account_number,
            bank_code,
        )
        return {
            'account_number': account_number,
            'account_name': STUB_ACCOUNT_NAME,
            'bank_id': 21,
        }
    return _request(
        'GET',
        '/bank/resolve',
        params={'account_number': account_number, 'bank_code': bank_code},
    )


def create_subaccount(business_name, bank_code, account_number, percentage_charge):
    """
    POST /subaccount — register a split-payment subaccount.

    ``percentage_charge`` is the platform's share of each transaction
    (Decimal, sent as float per Paystack's schema). Returns the created
    subaccount data including ``subaccount_code`` and ``settlement_bank``
    (the bank's display name).
    """
    payload = {
        'business_name': business_name,
        'settlement_bank': bank_code,
        'account_number': account_number,
        'percentage_charge': float(percentage_charge),
    }
    if gateway_stub_enabled():
        logger.warning(
            'PAYSTACK_STUB_GATEWAY: skipping live POST /subaccount %s', payload
        )
        return {
            'subaccount_code': STUB_SUBACCOUNT_CODE,
            'business_name': business_name,
            'settlement_bank': 'Zenith Bank',
            'account_number': account_number,
            'percentage_charge': float(percentage_charge),
            'is_verified': True,
            'active': True,
        }
    return _request('POST', '/subaccount', json=payload)


# ---------------------------------------------------------------------------
# Amount conversion — gateway boundary only. Never store kobo in the DB.
# ---------------------------------------------------------------------------

_KOBO = Decimal('100')
_NAIRA_QUANTUM = Decimal('0.01')


def naira_to_kobo(amount):
    """
    Convert a NGN Decimal to integer kobo (Paystack's subunit).

    Uses Decimal throughout — ``int(float_naira * 100)`` is forbidden
    (binary float cannot represent 0.10 exactly). Quantizes to kobo
    (2 decimal places) with ROUND_HALF_UP so ₦157500.50 → 15750050.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if amount < 0:
        raise ValueError('Amount cannot be negative.')
    naira = amount.quantize(_NAIRA_QUANTUM, rounding=ROUND_HALF_UP)
    kobo = (naira * _KOBO).to_integral_value(rounding=ROUND_HALF_UP)
    return int(kobo)


def kobo_to_naira(kobo):
    """Inverse of naira_to_kobo. Prompt 4 will use this when matching verify amounts."""
    return (Decimal(int(kobo)) / _KOBO).quantize(_NAIRA_QUANTUM)


def build_initialize_payload(*, email, amount_naira, reference, subaccount, metadata=None):
    """
    Exact JSON body sent to POST /transaction/initialize.

    ``amount`` is integer kobo. ``subaccount`` is the school's
    SchoolPaymentAccount.subaccount_code — Paystack splits at their end.
    ``bearer`` is omitted so Paystack's default applies (main/platform
    account bears Paystack fees). Currency is explicit NGN.
    """
    payload = {
        'email': email,
        'amount': naira_to_kobo(amount_naira),
        'currency': 'NGN',
        'reference': reference,
        'subaccount': subaccount,
    }
    if metadata:
        payload['metadata'] = metadata
    return payload


def initialize_transaction(*, email, amount_naira, reference, subaccount, metadata=None):
    """
    POST /transaction/initialize — returns Paystack ``data``
    (authorization_url, access_code, reference).

    Does not mark anything paid. Caller stores a pending Payment first.
    """
    payload = build_initialize_payload(
        email=email,
        amount_naira=amount_naira,
        reference=reference,
        subaccount=subaccount,
        metadata=metadata,
    )
    logger.info(
        'Paystack initialize-transaction payload: email=%s amount_kobo=%s '
        'reference=%s subaccount=%s currency=%s',
        payload['email'],
        payload['amount'],
        payload['reference'],
        payload['subaccount'],
        payload['currency'],
    )
    if gateway_stub_enabled():
        logger.warning(
            'PAYSTACK_STUB_GATEWAY: skipping live POST /transaction/initialize'
        )
        return {
            'authorization_url': (
                f'https://checkout.paystack.com/stub_{reference}'
            ),
            'access_code': f'stub_access_{reference}',
            'reference': reference,
        }
    return _request('POST', '/transaction/initialize', json=payload)


def verify_webhook_signature(payload, signature):
    """
    HMAC-SHA512 of the RAW request body using PAYSTACK_SECRET_KEY.

    ``payload`` MUST be the original ``request.body`` bytes — never a
    re-serialized dict. ``signature`` is the ``X-Paystack-Signature`` header.

    Returns False (fail closed) when the secret, signature, or payload is
    missing; never raises. Comparison is constant-time.
    """
    secret = getattr(settings, 'PAYSTACK_SECRET_KEY', None) or ''
    if not secret or not signature or not isinstance(payload, (bytes, bytearray)):
        return False
    computed = hmac.new(
        secret.encode('utf-8'),
        bytes(payload),
        hashlib.sha512,
    ).hexdigest()
    try:
        return hmac.compare_digest(computed, signature)
    except (TypeError, ValueError):
        return False


def verify_transaction(reference):
    """
    GET /transaction/verify/:reference — returns Paystack ``data``.

    Caller must still check ``data.status == 'success'`` AND that
    ``data.amount`` (integer kobo) matches the stored Payment. This function
    only talks to Paystack; it does not mark anything paid.
    """
    encoded = quote(str(reference), safe='')
    if gateway_stub_enabled():
        from finance.models import Payment

        logger.warning(
            'PAYSTACK_STUB_GATEWAY: skipping live GET /transaction/verify/%s',
            encoded,
        )
        payment = Payment.objects.filter(reference=reference).first()
        if payment is not None:
            amount_kobo = naira_to_kobo(payment.amount)
        else:
            from finance.models import PaymentCheckout

            checkout = PaymentCheckout.objects.filter(reference=reference).first()
            amount_kobo = naira_to_kobo(checkout.amount) if checkout is not None else 0
        return {
            'status': 'success',
            'amount': amount_kobo,
            'reference': reference,
            'currency': 'NGN',
            'paid_at': '2026-08-26T15:00:00.000Z',
        }
    return _request('GET', f'/transaction/verify/{encoded}')
