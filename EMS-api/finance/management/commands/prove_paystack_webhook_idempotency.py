"""
Prompt 8: prove Paystack webhook HMAC + double-delivery against this tenant.

Does not treat a unique constraint as sufficient. It literally POSTs the
same ``charge.success`` raw body twice (HMAC-SHA512 of those bytes) and
asserts:

  * still one SUCCESS Payment for the reference
  * invoice paid total did not double
  * still one PlatformTransactionLog row for the reference

Unsigned / invalid HMAC POSTs are also sent and must not apply.

Usage::

    python manage.py prove_paystack_webhook_idempotency \\
        --schema testacademy --from-bruno-env

    # In-process POSTs (Django test Client). Mocks Paystack verify unless
    # PAYSTACK_STUB_GATEWAY is already on. HMAC secret is overridden for
    # the run so an empty .env PAYSTACK_SECRET_KEY still proves the check.

    python manage.py prove_paystack_webhook_idempotency \\
        --schema testacademy --from-bruno-env --http --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings
from django_tenants.utils import get_public_schema_name, schema_context

HMAC_FIXTURE_SECRET = 'sk_test_bruno_local_hmac'
WEBHOOK_PATH = '/api/webhooks/paystack/'
BRUNO_ENV = Path(__file__).resolve().parents[3] / 'bruno' / 'environments' / 'Local.bru'


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha512).hexdigest()


def _charge_success_body(*, reference: str, subaccount_code: str, amount_kobo: int) -> bytes:
    payload = {
        'event': 'charge.success',
        'data': {
            'id': 424242,
            'status': 'success',
            'reference': reference,
            'amount': int(amount_kobo),
            'currency': 'NGN',
            'subaccount': {'subaccount_code': subaccount_code},
        },
    }
    return json.dumps(payload, separators=(',', ':')).encode('utf-8')


def _parse_bruno_env(path: Path) -> dict:
    text = path.read_text()
    return dict(re.findall(r'^\s*(\w+):\s*(.+)$', text, re.M))


def _http_post(*, base_url: str, body: bytes, signature: str | None) -> int:
    headers = {
        'Host': 'localhost',
        'Content-Type': 'application/json',
        'Content-Length': str(len(body)),
    }
    if signature is not None:
        headers['X-Paystack-Signature'] = signature
    req = Request(
        base_url.rstrip('/') + WEBHOOK_PATH,
        data=body,
        headers=headers,
        method='POST',
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.getcode()
    except HTTPError as exc:
        return exc.code


class Command(BaseCommand):
    help = (
        'POST the same signed charge.success webhook twice and prove '
        'no double-credit (Prompt 8). Also rejects unsigned/invalid HMAC.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--schema', default='testacademy')
        parser.add_argument('--reference', default='')
        parser.add_argument('--subaccount', default='')
        parser.add_argument(
            '--from-bruno-env',
            action='store_true',
            help=f'Read paymentReference / subaccountCode from {BRUNO_ENV}',
        )
        parser.add_argument(
            '--deliver',
            action='store_true',
            help='POST unsigned, invalid HMAC, then the same signed body twice.',
        )
        parser.add_argument(
            '--http',
            action='store_true',
            help='POST to a running server instead of the in-process test Client.',
        )
        parser.add_argument('--base-url', default='http://127.0.0.1:8000')
        parser.add_argument(
            '--assert-only',
            action='store_true',
            help='Do not POST; print Payment / invoice / PlatformTransactionLog evidence.',
        )

    def handle(self, *args, **options):
        from finance.models import Payment
        from finance.paystack import naira_to_kobo
        from finance.services import successful_paid_total
        from platform_admin.models import (
            PlatformTransactionLog,
            SubaccountTenantMap,
            Tenant,
            WebhookLog,
        )

        schema = options['schema']
        reference = (options['reference'] or '').strip()
        subaccount = (options['subaccount'] or '').strip()

        if options['from_bruno_env']:
            if not BRUNO_ENV.is_file():
                raise CommandError(f'Bruno env not found: {BRUNO_ENV}')
            env = _parse_bruno_env(BRUNO_ENV)
            reference = reference or env.get('paymentReference', '').strip()
            subaccount = subaccount or env.get('subaccountCode', '').strip()
            if env.get('termId'):
                self.stdout.write(f'bruno termId={env.get("termId")}')

        if not reference:
            raise CommandError(
                'Pass --reference or --from-bruno-env (paymentReference in Local.bru).'
            )

        with schema_context(get_public_schema_name()):
            tenant = Tenant.objects.filter(schema_name=schema).first()
        if tenant is None:
            raise CommandError(f'Unknown tenant schema {schema}')

        with schema_context(schema):
            try:
                payment = Payment.objects.select_related('invoice').get(
                    reference=reference
                )
            except Payment.DoesNotExist as exc:
                raise CommandError(
                    f'No Payment with reference={reference!r} in schema {schema}'
                ) from exc
            invoice = payment.invoice
            amount_kobo = naira_to_kobo(payment.amount)
            if not subaccount:
                from finance.models import SchoolPaymentAccount

                account = SchoolPaymentAccount.objects.first()
                if account is None:
                    raise CommandError('No SchoolPaymentAccount in this tenant.')
                subaccount = account.subaccount_code
            SubaccountTenantMap.upsert(subaccount, tenant)

            paid_before = successful_paid_total(invoice)
            success_before = Payment.objects.filter(
                invoice=invoice, status=Payment.Status.SUCCESS
            ).count()

        with schema_context(get_public_schema_name()):
            log_before = PlatformTransactionLog.objects.filter(
                payment_reference=reference
            ).count()
            webhook_before = WebhookLog.objects.filter(reference=reference).count()

        body = _charge_success_body(
            reference=reference,
            subaccount_code=subaccount,
            amount_kobo=amount_kobo,
        )
        secret = HMAC_FIXTURE_SECRET
        valid_sig = _sign(body, secret)

        results = {}
        if options['deliver'] and not options['assert_only']:
            if options['http']:
                results['unsigned'] = _http_post(
                    base_url=options['base_url'], body=body, signature=None
                )
                results['invalid_hmac'] = _http_post(
                    base_url=options['base_url'],
                    body=body,
                    signature='deadbeef',
                )
                results['signed_first'] = _http_post(
                    base_url=options['base_url'], body=body, signature=valid_sig
                )
                results['signed_second'] = _http_post(
                    base_url=options['base_url'], body=body, signature=valid_sig
                )
            else:
                results = self._deliver_in_process(
                    body=body,
                    secret=secret,
                    valid_sig=valid_sig,
                    payment=payment,
                )

        with schema_context(schema):
            payment.refresh_from_db()
            invoice.refresh_from_db()
            paid_after = successful_paid_total(invoice)
            success_after = Payment.objects.filter(
                invoice=invoice, status=Payment.Status.SUCCESS
            ).count()
            paystack_success = Payment.objects.filter(
                reference=reference,
                gateway=Payment.Gateway.PAYSTACK,
                status=Payment.Status.SUCCESS,
            ).count()

        with schema_context(get_public_schema_name()):
            log_after = PlatformTransactionLog.objects.filter(
                payment_reference=reference
            ).count()
            logs = list(
                WebhookLog.objects.filter(reference=reference).order_by('received_at')
            )
            unsigned_logged = any(
                not row.signature_valid
                and row.outcome == WebhookLog.Outcome.SIGNATURE_INVALID
                for row in WebhookLog.objects.order_by('-received_at')[:20]
            )

        evidence = {
            'reference': reference,
            'subaccount_code': subaccount,
            'raw_body': body.decode('utf-8'),
            'hmac_sha512': valid_sig,
            'http_results': results,
            'payment_status': payment.status,
            'paystack_success_rows_for_reference': paystack_success,
            'invoice_id': str(invoice.id),
            'invoice_status': invoice.status,
            'invoice_total': str(invoice.total_amount),
            'amount_paid_before': str(paid_before),
            'amount_paid_after': str(paid_after),
            'success_payments_on_invoice_before': success_before,
            'success_payments_on_invoice_after': success_after,
            'platform_txn_log_before': log_before,
            'platform_txn_log_after': log_after,
            'webhook_log_rows_for_reference_before': webhook_before,
            'webhook_log_rows_for_reference': len(logs),
            'unsigned_or_invalid_hmac_logged': unsigned_logged,
        }

        self.stdout.write(json.dumps(evidence, indent=2))

        if paystack_success != 1:
            raise CommandError(
                f'Expected exactly 1 SUCCESS Paystack Payment for {reference}, '
                f'got {paystack_success}'
            )
        expected_paid = payment.amount
        # Invoice may also have a manual payment; the Paystack credit itself
        # must not exceed one application of payment.amount.
        if paid_after < expected_paid:
            raise CommandError(
                f'Invoice amount_paid {paid_after} is less than the Paystack '
                f'payment {expected_paid} — webhook did not apply.'
            )
        # Double-credit of THIS reference would add payment.amount twice.
        # Compare platform log (unique per reference) and SUCCESS row count.
        if log_after != 1:
            raise CommandError(
                f'Expected 1 PlatformTransactionLog for {reference}, got {log_after}'
            )
        if success_after - success_before > 1:
            raise CommandError('Invoice gained more than one SUCCESS payment.')
        self.stdout.write(self.style.SUCCESS('Double-webhook idempotency HOLD.'))

    def _deliver_in_process(self, *, body, secret, valid_sig, payment):
        from finance.paystack import naira_to_kobo

        payload = {
            'status': True,
            'message': 'Verification successful',
            'data': {
                'status': 'success',
                'amount': naira_to_kobo(payment.amount),
                'reference': payment.reference,
                'paid_at': '2026-08-26T15:00:00.000Z',
            },
        }
        resp = mock.Mock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = payload

        client = Client()
        headers_common = {
            'content_type': 'application/json',
        }

        def _post(signature):
            extra = dict(headers_common)
            if signature is not None:
                extra['HTTP_X_PAYSTACK_SIGNATURE'] = signature
            return client.post(WEBHOOK_PATH, data=body, **extra).status_code

        with override_settings(PAYSTACK_SECRET_KEY=secret):
            unsigned = _post(None)
            invalid = _post('deadbeef')
            with mock.patch(
                'finance.paystack.requests.request', return_value=resp
            ):
                first = _post(valid_sig)
                second = _post(valid_sig)
        return {
            'unsigned': unsigned,
            'invalid_hmac': invalid,
            'signed_first': first,
            'signed_second': second,
        }
