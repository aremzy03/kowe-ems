from rest_framework.response import Response
from rest_framework.views import APIView

from platform_admin.permissions import IsPlatformAdmin
from platform_admin.services import InvalidRevenuePeriod, revenue_overview


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
