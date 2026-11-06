from django_tenants.utils import get_public_schema_name
from rest_framework.response import Response
from rest_framework.views import APIView

from platform_admin.models import Tenant, WebhookLog
from platform_admin.permissions import IsPlatformAdmin
from platform_admin.services import InvalidRevenuePeriod, revenue_overview

# Recent deliveries only. The stored payload is already clipped at write time;
# the list returns a shorter preview so a default GET cannot dump raw bodies.
WEBHOOK_LIST_LIMIT = 100
PAYLOAD_PREVIEW_LIMIT = 200
ERROR_MESSAGE_LIMIT = 280


def _money_as_api_string(value):
    from decimal import Decimal

    from rest_framework import serializers

    field = serializers.DecimalField(max_digits=12, decimal_places=2)
    if value is None:
        value = Decimal('0.00')
    return field.to_representation(value)


class PlatformRevenueOverviewView(APIView):
    """
    GET /api/platform/revenue/ — platform operator only (public host).

    Cross-tenant commission earned on Paystack fee payments, broken down
    by school. Optional ``from`` / ``to`` ISO dates (inclusive).
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        try:
            data = revenue_overview(
                from_raw=request.query_params.get('from') or '',
                to_raw=request.query_params.get('to') or '',
            )
        except InvalidRevenuePeriod as exc:
            return Response({'detail': str(exc)}, status=400)

        totals = data['totals']
        return Response(
            {
                'period': data['period'],
                'totals': {
                    'gross_amount': _money_as_api_string(totals['gross_amount']),
                    'commission_amount': _money_as_api_string(
                        totals['commission_amount']
                    ),
                    'net_to_school': _money_as_api_string(totals['net_to_school']),
                    'transaction_count': totals['transaction_count'],
                },
                'by_school': [
                    {
                        **row,
                        'gross_amount': _money_as_api_string(row['gross_amount']),
                        'commission_amount': _money_as_api_string(
                            row['commission_amount']
                        ),
                        'net_to_school': _money_as_api_string(row['net_to_school']),
                    }
                    for row in data['by_school']
                ],
            }
        )


def _clip(text, limit):
    text = text or ''
    if len(text) <= limit:
        return text
    return text[:limit]


def _primary_domain_name(tenant):
    domains = list(tenant.domains.all())
    if not domains:
        return None
    primary = next((domain for domain in domains if domain.is_primary), None)
    if primary is None:
        primary = min(domains, key=lambda domain: domain.domain)
    return primary.domain or None


def _tenant_slug(tenant, primary_domain):
    if primary_domain:
        return primary_domain.split('.')[0].lower()
    return tenant.schema_name.replace('_', '-')


class PlatformTenantListView(APIView):
    """
    GET /api/platform/tenants/ — platform operator only (public schema).

    Schools only. The public-schema tenant row is omitted. Read-only: this
    does not provision a school.
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        tenants = (
            Tenant.objects.exclude(schema_name=get_public_schema_name())
            .prefetch_related('domains')
            .order_by('school_name', 'schema_name')
        )
        results = []
        for tenant in tenants:
            primary_domain = _primary_domain_name(tenant)
            results.append(
                {
                    'id': str(tenant.id),
                    'school_name': tenant.school_name,
                    'schema_name': tenant.schema_name,
                    'slug': _tenant_slug(tenant, primary_domain),
                    'primary_domain': primary_domain,
                    'is_active': tenant.is_active,
                    'created_at': tenant.created_at,
                }
            )
        return Response({'count': len(results), 'results': results})


class PlatformWebhookLogListView(APIView):
    """
    GET /api/platform/webhooks/ — platform operator only (public schema).

    Newest ``WebhookLog`` rows. ``payload_preview`` and ``error_message``
    are truncated. This does not replay a delivery.
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        rows = (
            WebhookLog.objects.select_related('tenant')
            .order_by('-received_at', '-id')[:WEBHOOK_LIST_LIMIT]
        )
        results = [
            {
                'id': str(row.id),
                'received_at': row.received_at,
                'signature_valid': row.signature_valid,
                'event': row.event,
                'reference': row.reference,
                'subaccount_code': row.subaccount_code,
                'school_name': row.tenant.school_name if row.tenant_id else None,
                'outcome': row.outcome,
                'error_message': _clip(row.error_message, ERROR_MESSAGE_LIMIT),
                'payload_preview': _clip(row.payload, PAYLOAD_PREVIEW_LIMIT),
            }
            for row in rows
        ]
        return Response({'count': len(results), 'results': results})
