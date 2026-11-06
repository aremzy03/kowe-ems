import uuid

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin
from django_tenants.utils import get_public_schema_name, schema_context


class Tenant(TenantMixin):
    """
    School tenant (public schema). ``schema_name`` is inherited from TenantMixin.
    TenantMixin is abstract and does not define a primary key, so we use a UUID PK.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['school_name']

    def __str__(self):
        return self.school_name


class Domain(DomainMixin):
    """Standard django-tenants domain mapping (slug/hostname → Tenant lookup)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        ordering = ['domain']


class SubaccountTenantMap(models.Model):
    """
    Public-schema routing table: Paystack subaccount code → school Tenant.

    The global webhook hits the single API host (no school tenant header), so
    HeaderTenantMiddleware leaves the request on the public schema. After HMAC
    verification, the handler looks up this row in the public schema, THEN
    enters ``schema_context(tenant.schema_name)``.

    Written automatically when Prompt 1 onboarding successfully creates a
    Paystack subaccount (same success path as SchoolPaymentAccount).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subaccount_code = models.CharField(max_length=100, unique=True, db_index=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='paystack_subaccounts',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['subaccount_code']

    def __str__(self):
        return f'{self.subaccount_code} → {self.tenant.schema_name}'

    @classmethod
    def upsert(cls, subaccount_code, tenant):
        """
        Write (subaccount_code → tenant) in the PUBLIC schema.

        Safe to call from inside a tenant schema context (onboarding). Uses
        the tenant's PK so we do not pass a tenant-schema model instance
        into a public-schema query.
        """
        tenant_id = tenant.pk if hasattr(tenant, 'pk') else tenant
        with schema_context(get_public_schema_name()):
            obj, _created = cls.objects.update_or_create(
                subaccount_code=subaccount_code,
                defaults={'tenant_id': tenant_id},
            )
            return obj


class WebhookLog(models.Model):
    """
    Public-schema audit log for every Paystack webhook delivery.

    Rows are written even when HMAC fails or the subaccount cannot be
    mapped — a payment that silently fails to route here would never
    reach the school.
    """

    class Outcome(models.TextChoices):
        SIGNATURE_INVALID = 'signature_invalid', 'Signature invalid'
        INVALID_JSON = 'invalid_json', 'Invalid JSON'
        IGNORED_EVENT = 'ignored_event', 'Ignored event'
        UNKNOWN_SUBACCOUNT = 'unknown_subaccount', 'Unknown subaccount'
        MISSING_REFERENCE = 'missing_reference', 'Missing reference'
        APPLIED = 'applied', 'Applied'
        ERROR = 'error', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    signature_valid = models.BooleanField()
    event = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    subaccount_code = models.CharField(max_length=100, blank=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhook_logs',
    )
    outcome = models.CharField(max_length=32, choices=Outcome.choices, db_index=True)
    error_message = models.TextField(blank=True)
    payload = models.TextField(
        blank=True,
        help_text='Raw request body (truncated). Stored even when HMAC fails.',
    )

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.outcome} {self.event or "-"} {self.reference or "-"}'

    @classmethod
    def record(cls, **kwargs):
        """Insert a log row in the public schema regardless of current search_path."""
        with schema_context(get_public_schema_name()):
            return cls.objects.create(**kwargs)


class PlatformTransactionLog(models.Model):
    """
    Public-schema ledger of platform commission earned on Paystack fees.

    Written once per successful online payment from
    ``finance.services.verify_and_apply_payment`` (the shared apply path for
    the return-flow verify endpoint AND the global webhook). Manual cash /
    transfer recordings do not generate commission and must not write here.

    Living in the public schema means the platform revenue dashboard can
    aggregate across schools without iterating tenant schemas.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='platform_transactions',
    )
    payment_reference = models.CharField(max_length=100, unique=True, db_index=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_to_school = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-timestamp']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(gross_amount__gt=0),
                name='platform_txn_gross_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(commission_amount__gte=0),
                name='platform_txn_commission_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(net_to_school__gte=0),
                name='platform_txn_net_non_negative',
            ),
        ]

    def __str__(self):
        return f'{self.payment_reference} commission={self.commission_amount}'

    @classmethod
    def record_paystack_success(
        cls,
        *,
        tenant_id,
        payment_reference,
        gross_amount,
        commission_amount,
        net_to_school,
        timestamp,
    ):
        """
        Insert-or-ignore in the public schema.

        Unique on ``payment_reference`` so verify + webhook for the same
        Paystack charge cannot double-count commission. First write wins.
        """
        from django.db import IntegrityError
        from django.utils import timezone as dj_tz

        defaults = {
            'tenant_id': tenant_id,
            'gross_amount': gross_amount,
            'commission_amount': commission_amount,
            'net_to_school': net_to_school,
            'timestamp': timestamp or dj_tz.now(),
        }
        with schema_context(get_public_schema_name()):
            try:
                obj, _created = cls.objects.get_or_create(
                    payment_reference=payment_reference,
                    defaults=defaults,
                )
                return obj
            except IntegrityError:
                return cls.objects.get(payment_reference=payment_reference)
