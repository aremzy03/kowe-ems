"""
Public-schema platform services (cross-tenant; no school schema iteration).
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from platform_admin.models import PlatformTransactionLog

_ZERO = Decimal('0.00')
_MONEY = Decimal('0.01')
_MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)


class InvalidRevenuePeriod(Exception):
    """``from`` / ``to`` query params were not ISO dates or were inverted."""


def _money(value):
    if value is None:
        return _ZERO
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_MONEY)


def parse_revenue_period(from_raw, to_raw):
    """
    Inclusive calendar dates in the current timezone → aware [start, end).

    ``from_raw`` / ``to_raw`` are ISO date strings (YYYY-MM-DD) or empty.
    """
    start = None
    end_exclusive = None
    if from_raw:
        from_date = parse_date(from_raw)
        if from_date is None:
            raise InvalidRevenuePeriod('from must be an ISO date (YYYY-MM-DD).')
        start = timezone.make_aware(datetime.combine(from_date, time.min))
    if to_raw:
        to_date = parse_date(to_raw)
        if to_date is None:
            raise InvalidRevenuePeriod('to must be an ISO date (YYYY-MM-DD).')
        end_exclusive = timezone.make_aware(
            datetime.combine(to_date + timedelta(days=1), time.min)
        )
    if start is not None and end_exclusive is not None and start >= end_exclusive:
        raise InvalidRevenuePeriod('from must be on or before to.')
    return start, end_exclusive


def revenue_overview(*, from_raw='', to_raw=''):
    """
    Aggregate ``PlatformTransactionLog`` across all tenants.

    Returns totals plus a per-school breakdown. Does not enter tenant schemas.
    """
    start, end_exclusive = parse_revenue_period(from_raw, to_raw)
    qs = PlatformTransactionLog.objects.select_related('tenant').all()
    if start is not None:
        qs = qs.filter(timestamp__gte=start)
    if end_exclusive is not None:
        qs = qs.filter(timestamp__lt=end_exclusive)

    totals = qs.aggregate(
        gross_amount=Coalesce(Sum('gross_amount'), Value(_ZERO), output_field=_MONEY_FIELD),
        commission_amount=Coalesce(
            Sum('commission_amount'), Value(_ZERO), output_field=_MONEY_FIELD
        ),
        net_to_school=Coalesce(
            Sum('net_to_school'), Value(_ZERO), output_field=_MONEY_FIELD
        ),
        transaction_count=Count('id'),
    )

    by_school_qs = (
        qs.values('tenant_id', 'tenant__school_name', 'tenant__schema_name')
        .annotate(
            gross_amount=Coalesce(
                Sum('gross_amount'), Value(_ZERO), output_field=_MONEY_FIELD
            ),
            commission_amount=Coalesce(
                Sum('commission_amount'), Value(_ZERO), output_field=_MONEY_FIELD
            ),
            net_to_school=Coalesce(
                Sum('net_to_school'), Value(_ZERO), output_field=_MONEY_FIELD
            ),
            transaction_count=Count('id'),
        )
        .order_by('tenant__school_name')
    )

    by_school = [
        {
            'tenant_id': str(row['tenant_id']),
            'school_name': row['tenant__school_name'],
            'schema_name': row['tenant__schema_name'],
            'gross_amount': _money(row['gross_amount']),
            'commission_amount': _money(row['commission_amount']),
            'net_to_school': _money(row['net_to_school']),
            'transaction_count': row['transaction_count'],
        }
        for row in by_school_qs
    ]

    return {
        'period': {
            'from': from_raw or None,
            'to': to_raw or None,
        },
        'totals': {
            'gross_amount': _money(totals['gross_amount']),
            'commission_amount': _money(totals['commission_amount']),
            'net_to_school': _money(totals['net_to_school']),
            'transaction_count': totals['transaction_count'],
        },
        'by_school': by_school,
    }
