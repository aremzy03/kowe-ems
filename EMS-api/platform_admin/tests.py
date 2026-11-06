"""
Platform revenue overview (Phase 4, Prompt 7).

Lives on the public schema so it does not iterate tenant schemas.
Auth: ``User.is_platform_admin`` + login without a tenant header (no
SchoolMembership). School staff JWTs are 403 here.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework import status
from rest_framework.test import APIClient

from memberships.models import SchoolMembership
from platform_admin.models import PlatformTransactionLog, Tenant
from platform_admin.testing import set_tenant_slug

User = get_user_model()

REVENUE_URL = '/api/platform/revenue/'
LOGIN_URL = '/api/auth/login/'


class PlatformRevenueOverviewTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Test School'
        return tenant

    def setUp(self):
        super().setUp()
        # Public-host requests in a previous test can leave search_path on
        # the public schema; tenant fixtures must be written in this school.
        connection.set_tenant(self.tenant)
        self.operator = User.objects.create_user(
            email='operator@platform.example',
            password='pass12345',
            is_platform_admin=True,
        )
        self.school_admin = User.objects.create_user(
            email='admin-p7@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(
            user=self.school_admin,
            role=SchoolMembership.Role.ADMIN,
            is_active=True,
        )
        self.plain = User.objects.create_user(
            email='nobody@example.com',
            password='pass12345',
        )

        self.other_tenant = self._make_other_tenant()

        self.public = APIClient()
        self.tenant_api = APIClient()
        set_tenant_slug(self.tenant_api, self.tenant)

    def _make_other_tenant(self):
        with schema_context(get_public_schema_name()):
            other = Tenant(schema_name='other_p7_school', school_name='Other School')
            other.auto_create_schema = False
            other.save()
        connection.set_tenant(self.tenant)
        return other

    def _log(self, *, tenant, reference, gross, commission, net, when=None):
        with schema_context(get_public_schema_name()):
            row = PlatformTransactionLog.objects.create(
                tenant=tenant,
                payment_reference=reference,
                gross_amount=gross,
                commission_amount=commission,
                net_to_school=net,
                timestamp=when or timezone.now(),
            )
        connection.set_tenant(self.tenant)
        return row

    def test_platform_admin_sees_totals_broken_down_by_school(self):
        self._log(
            tenant=self.tenant,
            reference='pay_a',
            gross=Decimal('10000.00'),
            commission=Decimal('500.00'),
            net=Decimal('9500.00'),
        )
        self._log(
            tenant=self.tenant,
            reference='pay_b',
            gross=Decimal('2000.00'),
            commission=Decimal('100.00'),
            net=Decimal('1900.00'),
        )
        self._log(
            tenant=self.other_tenant,
            reference='pay_c',
            gross=Decimal('4000.00'),
            commission=Decimal('200.00'),
            net=Decimal('3800.00'),
        )

        self.public.force_authenticate(user=self.operator)
        response = self.public.get(REVENUE_URL)
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['totals']['gross_amount'], '16000.00')
        self.assertEqual(response.data['totals']['commission_amount'], '800.00')
        self.assertEqual(response.data['totals']['net_to_school'], '15200.00')
        self.assertEqual(response.data['totals']['transaction_count'], 3)

        by_name = {row['school_name']: row for row in response.data['by_school']}
        self.assertEqual(set(by_name), {'Test School', 'Other School'})
        self.assertEqual(by_name['Test School']['commission_amount'], '600.00')
        self.assertEqual(by_name['Test School']['transaction_count'], 2)
        self.assertEqual(by_name['Other School']['commission_amount'], '200.00')
        self.assertEqual(by_name['Other School']['schema_name'], 'other_p7_school')

    def test_time_period_filter(self):
        now = timezone.now()
        self._log(
            tenant=self.tenant,
            reference='pay_old',
            gross=Decimal('1000.00'),
            commission=Decimal('50.00'),
            net=Decimal('950.00'),
            when=now - timedelta(days=40),
        )
        self._log(
            tenant=self.tenant,
            reference='pay_new',
            gross=Decimal('3000.00'),
            commission=Decimal('150.00'),
            net=Decimal('2850.00'),
            when=now,
        )
        from_date = (now - timedelta(days=7)).date().isoformat()
        to_date = now.date().isoformat()

        self.public.force_authenticate(user=self.operator)
        response = self.public.get(REVENUE_URL, {'from': from_date, 'to': to_date})
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['period']['from'], from_date)
        self.assertEqual(response.data['period']['to'], to_date)
        self.assertEqual(response.data['totals']['transaction_count'], 1)
        self.assertEqual(response.data['totals']['commission_amount'], '150.00')

    def test_invalid_period_is_400(self):
        self.public.force_authenticate(user=self.operator)
        response = self.public.get(REVENUE_URL, {'from': 'not-a-date'})
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_school_staff_and_anonymous_are_forbidden(self):
        response = self.public.get(REVENUE_URL)
        connection.set_tenant(self.tenant)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        self.public.force_authenticate(user=self.school_admin)
        response = self.public.get(REVENUE_URL)
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.public.force_authenticate(user=self.plain)
        response = self.public.get(REVENUE_URL)
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_revenue_url_forbidden_on_tenant_schema(self):
        self.tenant_api.force_authenticate(user=self.operator)
        response = self.tenant_api.get(REVENUE_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_logs_in_on_public_schema_without_membership(self):
        response = self.public.post(
            LOGIN_URL,
            {'email': 'operator@platform.example', 'password': 'pass12345'},
            format='json',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['role'], 'platform_admin')
        self.assertFalse(response.data['requires_2fa'])

    def test_school_admin_cannot_log_in_without_tenant_slug(self):
        response = self.public.post(
            LOGIN_URL,
            {'email': 'admin-p7@example.com', 'password': 'pass12345'},
            format='json',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_admin_cannot_log_in_on_tenant_schema_without_membership(self):
        response = self.tenant_api.post(
            LOGIN_URL,
            {'email': 'operator@platform.example', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
