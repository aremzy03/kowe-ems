import uuid

from django.conf import settings
from django.db import models


class SchoolPaymentAccount(models.Model):
    """
    The school's verified settlement account for online fee collection.

    One row per gateway per school (tenant schema). A row is only created
    after BOTH Paystack calls succeed server-side:

      1. GET /bank/resolve  — confirms the account exists and returns the
         bank-registered account_name (fraud/typo guardrail; the stored
         account_name is always Paystack's resolved value, never admin input).
      2. POST /subaccount   — registers the split-payment subaccount using
         the platform secret key; the returned subaccount_code is what
         Prompt 3's transaction initialization will route payments through.

    ``platform_commission_pct`` maps to Paystack's ``percentage_charge``:
    the share of each transaction that stays with the PLATFORM (main)
    account; the remainder settles directly to this school's bank account.

    Money-safety: ``account_number`` is stored in full for gateway calls but
    must never leave the API unmasked — serializers expose last 4 digits only.
    """

    class Gateway(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(
        max_length=20,
        choices=Gateway.choices,
        default=Gateway.PAYSTACK,
    )
    subaccount_code = models.CharField(
        max_length=100,
        help_text='Paystack subaccount code (ACCT_...) returned by POST /subaccount.',
    )
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20)
    account_number = models.CharField(max_length=32)
    account_name = models.CharField(
        max_length=255,
        help_text='Bank-registered name resolved via GET /bank/resolve — not admin input.',
    )
    platform_commission_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text=(
            "Percentage of each transaction retained by the platform "
            "(Paystack subaccount percentage_charge)."
        ),
    )
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payment_accounts_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # One settlement account per gateway per school. Changing bank
            # details is a sensitive money operation and intentionally has no
            # self-service replace path yet.
            models.UniqueConstraint(
                fields=['gateway'],
                name='uniq_payment_account_per_gateway',
            ),
        ]

    def __str__(self):
        return f'{self.get_gateway_display()} {self.subaccount_code} ({self.bank_name})'

    @property
    def masked_account_number(self):
        return f'****{self.account_number[-4:]}' if self.account_number else ''


class FeeStructure(models.Model):
    """
    A single billable fee item for a term.

    ``class_level`` set: only that class (e.g. JSS1 / 1st term / Tuition).
    ``class_level`` null: every class in the term (textbook, uniform, bus).

    Invoice generation bills class fees as one itemized invoice and each
    school-wide fee as its own invoice, so a parent can pay them separately
    or together. Amounts are Decimal end-to-end — never float.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_level = models.ForeignKey(
        'academics.ClassLevel',
        on_delete=models.PROTECT,
        related_name='fee_structures',
        null=True,
        blank=True,
        help_text='Empty means the fee applies to every class in the term.',
    )
    term = models.ForeignKey(
        'academics.Term',
        on_delete=models.PROTECT,
        related_name='fee_structures',
    )
    name = models.CharField(
        max_length=100,
        help_text='What the charge is for, e.g. "Tuition", "PTA Levy", "Sports Fee".',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['term', 'class_level', 'name']
        constraints = [
            # No two fee items with the same name for the same class+term —
            # a duplicate would silently double-bill every invoice generated.
            # PostgreSQL treats NULL class_level as distinct, so school-wide
            # fees need their own constraint below.
            models.UniqueConstraint(
                fields=['class_level', 'term', 'name'],
                name='uniq_feestructure_class_term_name',
            ),
            models.UniqueConstraint(
                fields=['term', 'name'],
                condition=models.Q(class_level__isnull=True),
                name='uniq_feestructure_schoolwide_term_name',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='feestructure_amount_positive',
            ),
        ]

    def __str__(self):
        return f'{self.name} — {self.class_level} ({self.term}): {self.amount}'


class Invoice(models.Model):
    """
    A student's bill. Class fees for a term share one itemized invoice.
    Each school-wide fee (no class level) is its own invoice for that term,
    so it can be paid on its own or in the same Paystack checkout.

    Status lifecycle, driven by cumulative *successful* Payments only:
      unpaid → partially_paid → paid
    (Prompt 3 initialize never marks money received; Prompts 4/5 verify
    online payments, Prompt 6 records cash/transfer. All three must call
    the same ``recompute_invoice_payment_status`` helper.)

    Partial/installment payments ARE in MVP scope — Nigerian K-12 term
    fees are routinely settled in part-payments. Online initialize accepts
    any amount up to the outstanding balance; invoice status follows the
    cumulative success total, not "one checkout = paid".
    Invoices are always created 'unpaid'.
    """

    class Status(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PARTIALLY_PAID = 'partially_paid', 'Partially paid'
        PAID = 'paid', 'Paid'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    term = models.ForeignKey(
        'academics.Term',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name='invoice_total_amount_non_negative',
            ),
        ]

    def __str__(self):
        return f'Invoice {self.student} ({self.term}) — {self.total_amount} [{self.status}]'


class InvoiceLineItem(models.Model):
    """
    Itemized breakdown of an Invoice — one row per FeeStructure item, so a
    parent sees what they are being charged for, not just a lump sum.

    ``amount`` is a snapshot of the fee at generation time: editing a
    FeeStructure later must not silently change already-issued invoices.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='line_items',
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        related_name='invoice_line_items',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['invoice', 'fee_structure__name']
        constraints = [
            models.UniqueConstraint(
                fields=['invoice', 'fee_structure'],
                name='uniq_lineitem_invoice_feestructure',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name='lineitem_amount_non_negative',
            ),
        ]

    def __str__(self):
        return f'{self.fee_structure.name}: {self.amount} (invoice {self.invoice_id})'


class PaymentCheckout(models.Model):
    """
    One Paystack transaction that settles two or more invoices.

    The Paystack reference lives here. Each invoice still gets its own
    Payment row (the amount that credits that invoice), linked through
    ``checkout``. Single-invoice checkouts do not use this model: their
    Paystack reference stays on Payment, which is what verify and the
    webhook already look up.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payment_checkouts_initiated',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='paymentcheckout_amount_positive',
            ),
        ]

    def __str__(self):
        return f'{self.reference} {self.amount} [{self.status}]'


class Payment(models.Model):
    """
    One attempted (or completed) payment against an Invoice.

    Online (gateway=paystack): created ``pending`` by Prompt 3's initialize
    endpoint. ``success`` / ``failed`` and ``paid_at`` are set only after
    server-side Paystack verification (Prompt 4) or webhook (Prompt 5) —
    never because the frontend redirected back from checkout.

    ``reference`` is a random Paystack-safe token stored on this row. The
    (tenant, invoice) mapping lives here rather than being packed into the
    reference string: Paystack only allows alphanumeric plus ``-._=``, a
    random token cannot leak invoice IDs, and Prompt 8's double-webhook
    idempotency is this unique constraint (second apply of the same
    reference is a no-op, not a double-credit).

    Manual cash/transfer (Prompt 6): created already ``success`` with
    ``gateway='manual'``. The bursar is asserting the money was received —
    there is no Paystack verify. Invoice status still goes through the
    single writer ``recompute_invoice_payment_status``.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    class Gateway(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'
        MANUAL = 'manual', 'Manual'

    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    checkout = models.ForeignKey(
        PaymentCheckout,
        on_delete=models.PROTECT,
        related_name='payments',
        null=True,
        blank=True,
        help_text='Set when this row is one invoice inside a combined Paystack checkout.',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    gateway = models.CharField(
        max_length=20,
        choices=Gateway.choices,
        default=Gateway.PAYSTACK,
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        null=True,
        blank=True,
        help_text='How a manual payment was received. Null for Paystack checkouts.',
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payments_initiated',
        null=True,
        blank=True,
        help_text='The parent who started this online checkout. Null for manual recordings.',
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payments_recorded',
        null=True,
        blank=True,
        help_text='Bursar/admin who recorded a cash or bank-transfer payment.',
    )
    notes = models.TextField(blank=True, default='')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='payment_amount_positive',
            ),
            # Paystack rows are parent-initiated checkouts. Manual rows are
            # bursar-asserted receipts (method required, no parent initiator).
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(gateway='paystack')
                        & models.Q(initiated_by__isnull=False)
                        & models.Q(recorded_by__isnull=True)
                        & models.Q(method__isnull=True)
                    )
                    | (
                        models.Q(gateway='manual')
                        & models.Q(initiated_by__isnull=True)
                        & models.Q(recorded_by__isnull=False)
                        & models.Q(method__in=['cash', 'bank_transfer'])
                    )
                ),
                name='payment_gateway_fields_consistent',
            ),
        ]

    def __str__(self):
        return f'{self.reference} {self.amount} [{self.status}]'
