from decimal import Decimal

from rest_framework import serializers

from academics.models import ClassLevel, Term
from finance.models import (
    FeeStructure,
    Invoice,
    InvoiceLineItem,
    Payment,
    SchoolPaymentAccount,
)
from finance.services import invoice_outstanding, successful_paid_total

_MONEY_FIELD = serializers.DecimalField(max_digits=12, decimal_places=2)


def _money_as_api_string(value):
    """Serialize Decimal naira the same way model DecimalFields do (string)."""
    if value is None:
        value = Decimal('0.00')
    return _MONEY_FIELD.to_representation(value)


class SchoolPaymentAccountSerializer(serializers.ModelSerializer):
    """
    Read serializer. ``account_number`` is ALWAYS masked (last 4 digits) —
    the full number exists only for server-side gateway calls and must never
    be exposed through the API.
    """

    account_number = serializers.SerializerMethodField()

    class Meta:
        model = SchoolPaymentAccount
        fields = [
            'id',
            'gateway',
            'subaccount_code',
            'bank_name',
            'bank_code',
            'account_number',
            'account_name',
            'platform_commission_pct',
            'is_verified',
            'is_active',
            'created_at',
        ]
        read_only_fields = fields

    def get_account_number(self, obj):
        return obj.masked_account_number


class PaymentAccountOnboardSerializer(serializers.Serializer):
    """
    Input for payment-account onboarding.

    Deliberately narrow: the admin supplies routing details only. The stored
    account_name always comes from Paystack's /bank/resolve response, and the
    commission percentage always comes from the platform-wide setting — a
    school admin can influence neither. ``account_name`` here is an optional
    extra guardrail: when provided it must match the resolved name.
    """

    bank_code = serializers.CharField(max_length=20)
    account_number = serializers.CharField(max_length=32, min_length=6)
    account_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text='Optional confirmation; must match the bank-resolved name.',
    )

    def validate_account_number(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Account number must contain digits only.')
        return value

    def validate_bank_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Bank code must contain digits only.')
        return value


# ---------------------------------------------------------------------------
# Fee structures and invoicing (Prompt 2)
# ---------------------------------------------------------------------------


class FeeStructureSerializer(serializers.ModelSerializer):
    """Admin CRUD for fee items. Amount is Decimal (string in JSON) — never float."""

    class_level = serializers.PrimaryKeyRelatedField(
        queryset=ClassLevel.objects.all(),
        required=False,
        allow_null=True,
        help_text='Omit or null to bill every class in the term.',
    )
    class_level_name = serializers.CharField(
        source='class_level.name',
        read_only=True,
        allow_null=True,
    )
    term_name = serializers.CharField(source='term.name', read_only=True)
    session_name = serializers.CharField(source='term.session.name', read_only=True)
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )

    class Meta:
        model = FeeStructure
        fields = (
            'id',
            'class_level',
            'class_level_name',
            'term',
            'term_name',
            'session_name',
            'name',
            'amount',
        )
        read_only_fields = ('id', 'class_level_name', 'term_name', 'session_name')

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        if 'class_level' in attrs:
            class_level = attrs['class_level']
        else:
            class_level = instance.class_level if instance is not None else None
        term = attrs.get('term', instance.term if instance is not None else None)
        name = attrs.get('name', instance.name if instance is not None else None)
        if class_level is None and term is not None and name:
            existing = FeeStructure.objects.filter(
                class_level__isnull=True,
                term=term,
                name=name,
            )
            if instance is not None:
                existing = existing.exclude(pk=instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {
                        'name': (
                            'A school-wide fee with this name already exists for this term.'
                        )
                    }
                )
        return attrs


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    """One itemized charge on an invoice — the fee name and snapshotted amount."""

    name = serializers.CharField(source='fee_structure.name', read_only=True)

    class Meta:
        model = InvoiceLineItem
        fields = ('id', 'fee_structure', 'name', 'amount')
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Read-only invoice representation with itemized line items and current
    payment status. Used for both the generation response (admin/bursar)
    and the parent-facing invoice list.
    """

    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(
        source='student.admission_number', read_only=True
    )
    term_name = serializers.CharField(source='term.name', read_only=True)
    session_name = serializers.CharField(source='term.session.name', read_only=True)
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)
    amount_paid = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            'id',
            'student',
            'student_name',
            'admission_number',
            'term',
            'term_name',
            'session_name',
            'total_amount',
            'amount_paid',
            'outstanding_amount',
            'status',
            'line_items',
            'created_at',
        )
        read_only_fields = fields

    def get_student_name(self, obj):
        return f'{obj.student.last_name}, {obj.student.first_name}'

    def get_amount_paid(self, obj):
        # Prefer the list-view annotation to avoid N+1; fall back to a query.
        if hasattr(obj, 'amount_paid_total'):
            value = obj.amount_paid_total
        else:
            value = successful_paid_total(obj)
        return _money_as_api_string(value)

    def get_outstanding_amount(self, obj):
        if hasattr(obj, 'amount_paid_total'):
            remaining = obj.total_amount - obj.amount_paid_total
            if remaining < 0:
                remaining = Decimal('0.00')
        else:
            remaining = invoice_outstanding(obj)
        return _money_as_api_string(remaining)


class InvoiceGenerateSerializer(serializers.Serializer):
    """Input for bulk invoice generation.

    ``class_level`` bills that class. Omit it, or send null, to bill every
    class with active enrollments in the term.
    """

    class_level = serializers.PrimaryKeyRelatedField(
        queryset=ClassLevel.objects.all(),
        required=False,
        allow_null=True,
    )
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())


class InitializePaymentSerializer(serializers.Serializer):
    """
    Parent starts Paystack checkout.

    One invoice: ``invoice`` plus optional ``amount`` (naira). Omitted
    amount pays the outstanding balance. A provided amount must be a
    positive Decimal no greater than that outstanding balance.

    Several invoices: ``invoices`` (at least two). Each is paid in full
    for its current outstanding balance, in one Paystack charge. ``amount``
    is not accepted on a combined checkout.
    """

    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(),
        required=False,
        allow_null=True,
    )
    invoices = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(),
        many=True,
        required=False,
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        invoice = attrs.get('invoice')
        invoices = attrs.get('invoices') or []
        amount = attrs.get('amount')
        if invoice is not None and invoices:
            raise serializers.ValidationError(
                'Send either invoice or invoices, not both.'
            )
        if invoice is None and not invoices:
            raise serializers.ValidationError('Choose an invoice to pay.')
        if invoices:
            if amount is not None:
                raise serializers.ValidationError(
                    {
                        'amount': (
                            'A combined payment pays each invoice in full. '
                            'Omit amount.'
                        )
                    }
                )
            ids = [item.id for item in invoices]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError(
                    {'invoices': 'Each invoice can only be included once.'}
                )
            if len(invoices) < 2:
                raise serializers.ValidationError(
                    {
                        'invoices': (
                            'Select at least two invoices, or send a single invoice.'
                        )
                    }
                )
        return attrs


class VerifyPaymentSerializer(serializers.Serializer):
    """Frontend return-flow: the Paystack reference from the checkout redirect."""

    reference = serializers.CharField(max_length=100)


class RecordManualPaymentSerializer(serializers.Serializer):
    """
    Bursar/admin records cash or bank transfer against an invoice.

    Amount is required Decimal naira (installments in MVP). Method is how
    the money arrived. Notes are optional audit text.
    """

    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=2000,
    )


class InvoiceNestedPaymentSerializer(serializers.ModelSerializer):
    """
    Thin payment row nested on invoice retrieve / parent my-invoices.

    Status here is the payment's own status (pending / success / failed).
    Invoice ``amount_paid`` / ``status`` still count SUCCESS rows only —
    a pending Paystack checkout must not look like money received.
    """

    initiated_by_email = serializers.SerializerMethodField()
    recorded_by_email = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            'id',
            'amount',
            'reference',
            'status',
            'gateway',
            'method',
            'initiated_by',
            'initiated_by_email',
            'recorded_by',
            'recorded_by_email',
            'notes',
            'paid_at',
            'created_at',
        )
        read_only_fields = fields

    def get_initiated_by_email(self, obj):
        user = obj.initiated_by
        return user.email if user is not None else None

    def get_recorded_by_email(self, obj):
        user = obj.recorded_by
        return user.email if user is not None else None


class PaymentSerializer(InvoiceNestedPaymentSerializer):
    """Staff ledger row: payment plus the student / term on its invoice."""

    student = serializers.UUIDField(source='invoice.student_id', read_only=True)
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(
        source='invoice.student.admission_number', read_only=True
    )
    term = serializers.UUIDField(source='invoice.term_id', read_only=True)
    term_name = serializers.CharField(source='invoice.term.name', read_only=True)
    session_name = serializers.CharField(
        source='invoice.term.session.name', read_only=True
    )

    class Meta(InvoiceNestedPaymentSerializer.Meta):
        fields = InvoiceNestedPaymentSerializer.Meta.fields + (
            'invoice',
            'student',
            'student_name',
            'admission_number',
            'term',
            'term_name',
            'session_name',
        )
        read_only_fields = fields

    def get_student_name(self, obj):
        student = obj.invoice.student
        return f'{student.last_name}, {student.first_name}'


class InvoiceDetailSerializer(InvoiceSerializer):
    """Invoice retrieve: itemized charges plus every related payment."""

    payments = InvoiceNestedPaymentSerializer(many=True, read_only=True)

    class Meta(InvoiceSerializer.Meta):
        fields = InvoiceSerializer.Meta.fields + ('payments',)
        read_only_fields = fields
