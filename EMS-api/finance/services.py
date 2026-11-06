"""
Finance domain services.

Runs inside a tenant schema (django-tenants). Keep gateway orchestration
here — views stay thin.

``verify_and_apply_payment`` is the ONE shared verify+apply function
for Paystack. The Prompt 4 return-flow endpoint and Prompt 5's webhook
both call it. Do not add a second Paystack implementation.

Manual cash/transfer (Prompt 6) is not a Paystack verify: it creates a
SUCCESS Payment and calls ``recompute_invoice_payment_status`` — the
single invoice-status writer. Do not route cash through
``verify_and_apply_payment``.

``PlatformTransactionLog`` (public schema) is written in ONE place:
inside ``verify_and_apply_payment`` after a Paystack payment is marked
SUCCESS. The webhook and the return-flow endpoint both go through here,
so they cannot diverge. Manual recordings never write that log.
"""

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware

from academics.models import Enrollment
from finance.models import (
    FeeStructure,
    Invoice,
    InvoiceLineItem,
    Payment,
    SchoolPaymentAccount,
)
from finance.paystack import (
    create_subaccount,
    initialize_transaction,
    naira_to_kobo,
    resolve_bank_account,
    verify_transaction,
)

logger = logging.getLogger(__name__)


class PaymentAccountExists(Exception):
    """This school already has a payment account for the gateway."""


class OnlinePaymentsUnavailable(Exception):
    """School has no active, verified SchoolPaymentAccount — no online checkout."""


class PaymentAmountMismatch(Exception):
    """Paystack's verified kobo amount does not match the stored Payment."""


def get_active_payment_account(gateway=SchoolPaymentAccount.Gateway.PAYSTACK):
    """
    The school's verified, active settlement account, or None.

    Prompt 3's online payment initialization MUST call this and refuse to
    initialize when it returns None (manual payment recording only until
    onboarding is completed).
    """
    return SchoolPaymentAccount.objects.filter(
        gateway=gateway,
        is_verified=True,
        is_active=True,
    ).first()


def _normalize_name(name):
    """Token-sorted, casefolded form so 'John Doe' == 'DOE JOHN'."""
    return sorted(name.casefold().split())


def onboard_school_payment_account(
    *,
    bank_code,
    account_number,
    created_by,
    expected_account_name=None,
):
    """
    Resolve bank details → create Paystack subaccount → store, atomically.

    Order matters and must not change:
      1. GET /bank/resolve confirms the account exists; its resolved
         account_name is the only name we ever store (fraud/typo guardrail).
         If ``expected_account_name`` is provided, a normalized mismatch
         aborts BEFORE any subaccount is created.
      2. POST /subaccount registers the split subaccount with the platform
         commission percentage (platform-wide setting, never admin input).
      3. Only then is SchoolPaymentAccount persisted, already verified and
         active. A failure at any earlier step stores nothing.

    Raises PaymentAccountExists, ValidationError, or finance.paystack.PaystackError.
    """
    gateway = SchoolPaymentAccount.Gateway.PAYSTACK
    if SchoolPaymentAccount.objects.filter(gateway=gateway).exists():
        raise PaymentAccountExists(
            'A payment account already exists for this school. '
            'Contact platform support to change bank details.'
        )

    resolved = resolve_bank_account(account_number, bank_code)
    resolved_name = (resolved.get('account_name') or '').strip()
    if not resolved_name:
        raise ValidationError(
            {'account_number': 'Bank did not return an account name; cannot verify.'}
        )

    if expected_account_name and _normalize_name(expected_account_name) != _normalize_name(
        resolved_name
    ):
        raise ValidationError(
            {
                'account_name': (
                    f'Account name mismatch: bank has "{resolved_name}". '
                    'Confirm the bank code and account number are correct.'
                )
            }
        )

    commission_pct = settings.PLATFORM_COMMISSION_PCT
    subaccount = create_subaccount(
        business_name=connection.tenant.school_name,
        bank_code=bank_code,
        account_number=account_number,
        percentage_charge=commission_pct,
    )
    subaccount_code = subaccount.get('subaccount_code')
    if not subaccount_code:
        raise ValidationError(
            {'detail': 'Gateway did not return a subaccount code; account not saved.'}
        )

    with transaction.atomic():
        account = SchoolPaymentAccount.objects.create(
            gateway=gateway,
            subaccount_code=subaccount_code,
            # settlement_bank in the create-subaccount response is the bank's
            # display name (e.g. "Zenith Bank"); fall back to the code.
            bank_name=subaccount.get('settlement_bank') or bank_code,
            bank_code=bank_code,
            account_number=account_number,
            account_name=resolved_name,
            platform_commission_pct=commission_pct,
            is_verified=True,
            is_active=True,
            created_by=created_by,
        )
        # Public-schema routing for the global webhook: same success path as
        # the tenant-scoped SchoolPaymentAccount, so a school that is
        # onboarded is immediately resolvable by subaccount_code.
        from platform_admin.models import SubaccountTenantMap

        SubaccountTenantMap.upsert(subaccount_code, connection.tenant)

    return account


@transaction.atomic
def generate_invoices_for_class_term(*, class_level, term):
    """
    Create one Invoice (+ itemized InvoiceLineItems) per actively-enrolled
    student in ``class_level`` + ``term`` who does not already have an
    invoice for that term.

    Idempotent by design: students with an existing invoice for the term are
    skipped, never duplicated — so this can be safely re-run after adding
    late enrollees. The DB unique constraint on (student, term) backstops
    the application-level skip.

    Invoices are created with status='unpaid' and total_amount as the
    Decimal sum of the class+term FeeStructure items; each line item
    snapshots the fee amount at generation time.

    This function is one transaction. The invoice-generated receiver
    enqueues on commit, so the parent message is queued only after the
    line items in this same transaction are durable. Keep the invoice
    insert and its line items inside this atomic block.

    Returns {'created': [Invoice, ...], 'skipped_student_ids': [...],
    'fee_structures': [FeeStructure, ...]}.

    Raises ValidationError when no FeeStructure exists for the class+term
    (an empty/zero invoice would be meaningless and likely admin error).
    """
    fee_items = list(
        FeeStructure.objects.filter(class_level=class_level, term=term).order_by('name')
    )
    if not fee_items:
        raise ValidationError(
            {
                'detail': (
                    'No fee structures exist for this class level and term. '
                    'Create fee items before generating invoices.'
                )
            }
        )
    total = sum((f.amount for f in fee_items), Decimal('0.00'))

    student_ids = list(
        Enrollment.objects.filter(
            class_level=class_level,
            term=term,
            status=Enrollment.Status.ACTIVE,
        ).values_list('student_id', flat=True)
    )
    already_invoiced = set(
        Invoice.objects.filter(
            term=term,
            student_id__in=student_ids,
        ).values_list('student_id', flat=True)
    )

    created = []
    for student_id in student_ids:
        if student_id in already_invoiced:
            continue
        invoice = Invoice.objects.create(
            student_id=student_id,
            term=term,
            total_amount=total,
            status=Invoice.Status.UNPAID,
        )
        InvoiceLineItem.objects.bulk_create(
            InvoiceLineItem(invoice=invoice, fee_structure=fee, amount=fee.amount)
            for fee in fee_items
        )
        created.append(invoice)

    return {
        'created': created,
        'skipped_student_ids': sorted(already_invoiced, key=str),
        'fee_structures': fee_items,
    }


# ---------------------------------------------------------------------------
# Payments (Prompt 3 initialize; Prompts 4/5/6 apply)
# ---------------------------------------------------------------------------
#
# Invoice status is a function of cumulative SUCCESS payments only:
#   paid_total == 0                         → unpaid
#   0 < paid_total < invoice.total_amount   → partially_paid
#   paid_total >= invoice.total_amount      → paid
#
# Initialize NEVER calls recompute_invoice_payment_status — a pending
# checkout is not money received.


def successful_paid_total(invoice):
    """
    Sum of SUCCESS payments on this invoice (Decimal naira).

    Always queries — never trusts a queryset annotation — so initialize
    and ``recompute_invoice_payment_status`` cannot use a stale total.
    Pending/failed payments are ignored.
    """
    total = invoice.payments.filter(status=Payment.Status.SUCCESS).aggregate(
        total=Sum('amount')
    )['total']
    return total if total is not None else Decimal('0.00')


def invoice_outstanding(invoice):
    """Remaining naira due. Floors at 0.00 if somehow overpaid."""
    remaining = invoice.total_amount - successful_paid_total(invoice)
    return remaining if remaining > 0 else Decimal('0.00')


def paid_amount_annotation():
    """
    Annotate Invoice querysets with ``amount_paid_total`` so list serializers
    don't N+1. Pending payments do not count.
    """
    return Coalesce(
        Sum(
            'payments__amount',
            filter=Q(payments__status=Payment.Status.SUCCESS),
        ),
        Value(Decimal('0.00')),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def recompute_invoice_payment_status(invoice):
    """
    Single invoice-status writer for Prompts 4, 5, and 6.

    Do not duplicate this branching in the verify endpoint, the webhook,
    or manual recording. Initialize (Prompt 3) must not call this.

    Returns the invoice (possibly with an updated status).
    """
    paid = successful_paid_total(invoice)
    if paid <= 0:
        new_status = Invoice.Status.UNPAID
    elif paid >= invoice.total_amount:
        new_status = Invoice.Status.PAID
    else:
        new_status = Invoice.Status.PARTIALLY_PAID
    if invoice.status != new_status:
        invoice.status = new_status
        invoice.save(update_fields=['status'])
    return invoice


def _commission_split(gross, pct):
    """
    Platform share of a Paystack payment (Decimal naira).

    ``percentage_charge`` is applied by Paystack in kobo; this is the
    matching naira split we persist on PlatformTransactionLog for the
    dashboard. ROUND_HALF_UP so ₦0.005 does not banker's-round away.
    """
    gross = gross if isinstance(gross, Decimal) else Decimal(str(gross))
    pct = pct if isinstance(pct, Decimal) else Decimal(str(pct))
    commission = (gross * pct / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    net = (gross - commission).quantize(Decimal('0.01'))
    return commission, net


def _current_school_tenant_id():
    """
    PK of the school Tenant for the current connection.

    ``schema_context(schema_name)`` (the webhook) sets a FakeTenant that
    has ``schema_name`` but no ``pk``. Look the row up in the public
    schema when that happens.
    """
    from django_tenants.utils import get_public_schema_name, schema_context
    from platform_admin.models import Tenant

    tenant = getattr(connection, 'tenant', None)
    if tenant is None:
        return None
    schema_name = getattr(tenant, 'schema_name', None)
    if not schema_name or schema_name == get_public_schema_name():
        return None
    tenant_id = getattr(tenant, 'pk', None)
    if tenant_id is not None:
        return tenant_id
    with schema_context(get_public_schema_name()):
        return (
            Tenant.objects.filter(schema_name=schema_name)
            .values_list('id', flat=True)
            .first()
        )


def _record_platform_transaction_log(payment):
    """
    Write PlatformTransactionLog for a Paystack SUCCESS payment.

    Public schema, unique on payment_reference — safe to call on the
    idempotent already-SUCCESS path (first write wins). Must not be
    called from ``record_manual_payment``.
    """
    from platform_admin.models import PlatformTransactionLog

    tenant_id = _current_school_tenant_id()
    if tenant_id is None:
        logger.error(
            'Cannot write PlatformTransactionLog without a school tenant '
            '(reference=%s schema=%s)',
            payment.reference,
            getattr(getattr(connection, 'tenant', None), 'schema_name', None),
        )
        return None

    account = SchoolPaymentAccount.objects.filter(
        gateway=SchoolPaymentAccount.Gateway.PAYSTACK,
    ).first()
    pct = (
        account.platform_commission_pct
        if account is not None
        else settings.PLATFORM_COMMISSION_PCT
    )
    commission, net = _commission_split(payment.amount, pct)
    return PlatformTransactionLog.record_paystack_success(
        tenant_id=tenant_id,
        payment_reference=payment.reference,
        gross_amount=payment.amount,
        commission_amount=commission,
        net_to_school=net,
        timestamp=payment.paid_at or timezone.now(),
    )


def _paid_at_from_gateway(data):
    """Parse Paystack paid_at / paidAt; fall back to now if missing/unparseable."""
    raw = data.get('paid_at') or data.get('paidAt')
    if not raw or not isinstance(raw, str):
        return timezone.now()
    dt = parse_datetime(raw.replace('Z', '+00:00'))
    if dt is None:
        return timezone.now()
    if is_naive(dt):
        dt = make_aware(dt)
    return dt


def verify_and_apply_payment(reference):
    """
    Single verify-and-apply entry point for Paystack payments.

    Signature (stable — Prompt 5's webhook must call this, not a copy)::

        verify_and_apply_payment(reference: str) -> Payment

    Callers:
      * Prompt 4 return-flow: ``POST /api/finance/payments/verify/``
        looks up the Payment, checks the parent is linked to the student,
        then calls this.
      * Prompt 5 webhook: after HMAC on raw ``request.body``, public-schema
        SubaccountTenantMap lookup, and ``schema_context(tenant.schema_name)``,
        call ``verify_and_apply_payment(reference)``. Do not duplicate verify /
        amount-match / SUCCESS apply / invoice recompute in the webhook.

    Behaviour:
      1. Load Payment by unique ``reference`` (the tenant/invoice mapping).
      2. If ``status`` is already SUCCESS, return immediately — applying
         the same reference twice must not double-count.
      3. GET /transaction/verify/:reference (server-side; never trust the
         frontend redirect).
      4. Compare Paystack ``data.amount`` (integer kobo) to
         ``naira_to_kobo(Payment.amount)``.
      5. On success + match: mark SUCCESS, set ``paid_at``, then
         ``recompute_invoice_payment_status(invoice)``, then write
         ``PlatformTransactionLog`` (public schema). The log is the
         platform commission ledger — webhook and return-flow share this
         write because they share this function.
      6. On non-success gateway status: mark FAILED; invoice is unchanged
         because only SUCCESS totals count.

    Raises Payment.DoesNotExist, PaystackError, PaymentAmountMismatch,
    ValidationError (non-paystack gateway — Prompt 6 cash/transfer must
    not call this).
    """
    payment = Payment.objects.select_related('invoice').get(reference=reference)

    if payment.gateway != Payment.Gateway.PAYSTACK:
        raise ValidationError(
            {'detail': 'This payment cannot be verified with the online gateway.'}
        )

    if payment.status == Payment.Status.SUCCESS:
        _record_platform_transaction_log(payment)
        return payment

    data = verify_transaction(payment.reference)
    gateway_status = (data.get('status') or '').lower()
    try:
        gateway_kobo = int(data.get('amount'))
    except (TypeError, ValueError):
        gateway_kobo = None
    expected_kobo = naira_to_kobo(payment.amount)

    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status == Payment.Status.SUCCESS:
            _record_platform_transaction_log(locked)
            return locked

        if gateway_status != 'success':
            locked.status = Payment.Status.FAILED
            locked.save(update_fields=['status'])
            return locked

        if gateway_kobo != expected_kobo:
            logger.warning(
                'Paystack amount mismatch for reference=%s expected_kobo=%s '
                'gateway_kobo=%s',
                locked.reference,
                expected_kobo,
                gateway_kobo,
            )
            locked.status = Payment.Status.FAILED
            locked.save(update_fields=['status'])
            amount_mismatch = True
        else:
            amount_mismatch = False
            invoice = Invoice.objects.select_for_update().get(pk=locked.invoice_id)
            locked.status = Payment.Status.SUCCESS
            locked.paid_at = _paid_at_from_gateway(data)
            locked.save(update_fields=['status', 'paid_at'])
            recompute_invoice_payment_status(invoice)
            _record_platform_transaction_log(locked)

    # Raise after the atomic block commits so FAILED is persisted — raising
    # inside atomic would roll the status update back to pending.
    if amount_mismatch:
        raise PaymentAmountMismatch(
            'Verified amount does not match the payment on record.'
        )
    return locked


def _new_payment_reference():
    """
    Random Paystack-safe reference (alphanumeric + underscore).

    We do NOT encode tenant/invoice into the string: Paystack's charset is
    ``[A-Za-z0-9-._=]`` only, packing UUIDs/schema names is brittle, a
    random token does not leak invoice IDs, and the Payment row is the
    mapping Prompt 5/8 will look up by unique ``reference``.
    """
    return f'pay_{uuid.uuid4().hex}'


def _new_manual_payment_reference():
    """
    Unique reference for bursar-recorded cash/transfer.

    Prefixed ``manual-`` so it cannot collide with Paystack ``pay_`` tokens
    while still sitting on the same unique ``Payment.reference`` column.
    """
    return f'manual-{uuid.uuid4().hex}'


@transaction.atomic
def record_manual_payment(*, invoice, amount, method, recorded_by, notes=''):
    """
    Bursar/admin asserts cash or bank transfer was received.

    Creates a SUCCESS Payment with ``gateway='manual'`` (no Paystack call)
    and then calls ``recompute_invoice_payment_status`` — the same invoice
    status writer Prompts 4 and 5 use after a verified online payment.

    Do **not** send cash through the Paystack verify-and-apply path: that
    function is gateway verify + kobo amount-match. Cash is not a Paystack
    transaction and does not write ``PlatformTransactionLog``.

    ``amount`` is required Decimal naira. Installments are in MVP: any
    0.01 ≤ amount ≤ outstanding is accepted. Already-paid invoices and
    amounts above outstanding are rejected.

    Online checkout is not required — this is the fallback when the
    school has no SchoolPaymentAccount.

    Raises ValidationError for amount / method / already-paid cases.
    """
    if method not in Payment.Method.values:
        raise ValidationError({'method': 'Choose cash or bank_transfer.'})

    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    outstanding = invoice_outstanding(locked)
    if outstanding <= 0:
        raise ValidationError({'detail': 'This invoice is already paid in full.'})

    charge = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    charge = charge.quantize(Decimal('0.01'))
    if charge <= 0:
        raise ValidationError({'amount': 'Amount must be greater than zero.'})
    if charge > outstanding:
        raise ValidationError(
            {
                'amount': (
                    f'Amount exceeds the outstanding balance of {outstanding}.'
                )
            }
        )

    payment = Payment.objects.create(
        invoice=locked,
        amount=charge,
        reference=_new_manual_payment_reference(),
        status=Payment.Status.SUCCESS,
        gateway=Payment.Gateway.MANUAL,
        method=method,
        initiated_by=None,
        recorded_by=recorded_by,
        notes=notes or '',
        paid_at=timezone.now(),
    )
    recompute_invoice_payment_status(locked)
    return payment


def initialize_invoice_payment(*, invoice, parent, amount=None):
    """
    Start a Paystack checkout for ``invoice`` on behalf of ``parent``.

    ``amount`` is optional Decimal naira; omitted/None means "pay the
    outstanding balance in full". Partial amounts are allowed (MVP
    installment decision) as long as 0.01 <= amount <= outstanding.

    Creates a pending Payment, then calls Paystack. Does NOT change
    Invoice.status and does NOT set Payment.status to success.

    If a pending Paystack checkout already exists for this invoice it is
    superseded (marked failed) so a parent who closed the tab can retry
    without locking the balance. Only SUCCESS payments reduce outstanding.

    Raises OnlinePaymentsUnavailable when the school has no active
    verified SchoolPaymentAccount. Raises ValidationError for amount /
    already-paid / zero-outstanding cases. Raises PaystackError on
    gateway failure (the pending row is then marked failed).
    """
    account = get_active_payment_account()
    if account is None:
        raise OnlinePaymentsUnavailable(
            'Online fee payment is not available until this school '
            'verifies a settlement account. Pay at the bursar in the meantime.'
        )
    if not parent.email:
        raise ValidationError({'detail': 'A parent email is required to start checkout.'})

    with transaction.atomic():
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        outstanding = invoice_outstanding(locked)
        if outstanding <= 0:
            raise ValidationError({'detail': 'This invoice is already paid in full.'})

        if amount is None:
            charge = outstanding
        else:
            charge = amount if isinstance(amount, Decimal) else Decimal(str(amount))
            charge = charge.quantize(Decimal('0.01'))

        if charge <= 0:
            raise ValidationError({'amount': 'Amount must be greater than zero.'})
        if charge > outstanding:
            raise ValidationError(
                {
                    'amount': (
                        f'Amount exceeds the outstanding balance of {outstanding}.'
                    )
                }
            )

        # One in-flight Paystack checkout per invoice. Abandoned tabs must
        # not block a retry; SUCCESS rows are untouched.
        Payment.objects.filter(
            invoice=locked,
            gateway=Payment.Gateway.PAYSTACK,
            status=Payment.Status.PENDING,
        ).update(status=Payment.Status.FAILED)

        payment = Payment.objects.create(
            invoice=locked,
            amount=charge,
            reference=_new_payment_reference(),
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=parent,
            paid_at=None,
        )

    try:
        data = initialize_transaction(
            email=parent.email,
            amount_naira=payment.amount,
            reference=payment.reference,
            subaccount=account.subaccount_code,
            metadata={
                'invoice_id': str(locked.id),
                'student_id': str(locked.student_id),
            },
        )
    except Exception:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        raise

    authorization_url = data.get('authorization_url')
    if not authorization_url:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        raise ValidationError(
            {'detail': 'Gateway did not return a checkout URL; payment not started.'}
        )

    # Invoice.status stays as it was (unpaid / partially_paid). Paid_at
    # stays null. Prompt 4/5 (verify/webhook) mark Paystack success;
    # Prompt 6 records cash/transfer as SUCCESS without going through here.
    return payment, data


# ---------------------------------------------------------------------------
# School collection dashboard (Prompt 7)
# ---------------------------------------------------------------------------


def _collection_rate(collected, invoiced):
    if invoiced is None or invoiced <= 0:
        return Decimal('0.00')
    return (collected * Decimal('100') / invoiced).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def _bucket_totals():
    return {
        'invoiced_total': Decimal('0.00'),
        'collected_total': Decimal('0.00'),
        'outstanding_total': Decimal('0.00'),
        'invoice_count': 0,
        'paid_count': 0,
        'partially_paid_count': 0,
        'unpaid_count': 0,
    }


def _add_invoice_to_bucket(bucket, *, total_amount, collected, status):
    outstanding = total_amount - collected
    if outstanding < 0:
        outstanding = Decimal('0.00')
    bucket['invoiced_total'] += total_amount
    bucket['collected_total'] += collected
    bucket['outstanding_total'] += outstanding
    bucket['invoice_count'] += 1
    if status == Invoice.Status.PAID:
        bucket['paid_count'] += 1
    elif status == Invoice.Status.PARTIALLY_PAID:
        bucket['partially_paid_count'] += 1
    else:
        bucket['unpaid_count'] += 1


def _finalize_bucket(bucket):
    invoiced = bucket['invoiced_total']
    collected = bucket['collected_total']
    return {
        **bucket,
        'invoiced_total': invoiced.quantize(Decimal('0.01')),
        'collected_total': collected.quantize(Decimal('0.01')),
        'outstanding_total': bucket['outstanding_total'].quantize(Decimal('0.01')),
        'collection_rate': _collection_rate(collected, invoiced),
    }


def current_active_term():
    from academics.models import Term

    return Term.objects.filter(is_active=True).select_related('session').first()


def collection_dashboard_for_term(term):
    """
    Outstanding balance, collection rate (collected vs invoiced), by class.

    Current-term school dashboard for admin/bursar. Manual and Paystack
    SUCCESS payments both count — this is collections, not platform
    commission. Grouping uses the student's Enrollment.class_level for
    the same term as the invoice.
    """
    from academics.models import Enrollment

    invoices = list(
        Invoice.objects.filter(term=term)
        .annotate(amount_paid_total=paid_amount_annotation())
        .values('student_id', 'total_amount', 'amount_paid_total', 'status')
    )
    enrollments = {
        row['student_id']: row
        for row in Enrollment.objects.filter(term=term).values(
            'student_id', 'class_level_id', 'class_level__name'
        )
    }

    overall = _bucket_totals()
    by_class = {}
    class_order = []

    for inv in invoices:
        total = inv['total_amount']
        collected = inv['amount_paid_total'] or Decimal('0.00')
        _add_invoice_to_bucket(
            overall, total_amount=total, collected=collected, status=inv['status']
        )
        enrollment = enrollments.get(inv['student_id'])
        if enrollment is None:
            key = None
            name = 'Unassigned'
        else:
            key = enrollment['class_level_id']
            name = enrollment['class_level__name']
        if key not in by_class:
            by_class[key] = {**_bucket_totals(), 'class_level_id': key, 'class_level_name': name}
            class_order.append(key)
        _add_invoice_to_bucket(
            by_class[key],
            total_amount=total,
            collected=collected,
            status=inv['status'],
        )

    # Stable class order by name (Unassigned last).
    named = sorted(
        (k for k in class_order if k is not None),
        key=lambda k: by_class[k]['class_level_name'],
    )
    ordered_keys = named + ([None] if None in by_class else [])

    return {
        'term': term,
        'overall': _finalize_bucket(overall),
        'by_class': [
            {
                'class_level_id': (
                    str(by_class[k]['class_level_id'])
                    if by_class[k]['class_level_id'] is not None
                    else None
                ),
                'class_level_name': by_class[k]['class_level_name'],
                **{
                    key: value
                    for key, value in _finalize_bucket(by_class[k]).items()
                    if key not in ('class_level_id', 'class_level_name')
                },
            }
            for k in ordered_keys
        ],
    }
