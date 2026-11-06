"""GET /api/auth/me/ and login ``me`` profile payload."""

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from memberships.models import SchoolMembership
from platform_admin.testing import set_tenant_slug

User = get_user_model()

ME_URL = '/api/auth/me/'
LOGIN_URL = '/api/auth/login/'


class CurrentUserMeTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Auth School'
        return tenant

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='admin-me@example.com',
            password='pass12345',
            first_name='Ada',
            last_name='Admin',
        )
        self.teacher = User.objects.create_user(
            email='teacher-me@example.com',
            password='pass12345',
            first_name='Tunde',
            last_name='Teacher',
        )
        self.bursar = User.objects.create_user(
            email='bursar-me@example.com',
            password='pass12345',
            first_name='Bisi',
            last_name='Bursar',
        )
        self.parent = User.objects.create_user(
            email='parent-me@example.com',
            password='pass12345',
            first_name='Pat',
            last_name='Parent',
        )
        self.admin_membership = SchoolMembership.objects.create(
            user=self.admin,
            role=SchoolMembership.Role.ADMIN,
            is_active=True,
        )
        self.teacher_membership = SchoolMembership.objects.create(
            user=self.teacher,
            role=SchoolMembership.Role.TEACHER,
            is_active=True,
        )
        self.bursar_membership = SchoolMembership.objects.create(
            user=self.bursar,
            role=SchoolMembership.Role.BURSAR,
            is_active=True,
        )
        self.parent_membership = SchoolMembership.objects.create(
            user=self.parent,
            role=SchoolMembership.Role.PARENT,
            is_active=True,
        )
        self.api = APIClient()
        set_tenant_slug(self.api, self.tenant)

    def _as(self, user):
        self.api.force_authenticate(user=user)
        return self.api

    def _assert_school_me(self, data, *, user, membership):
        self.assertEqual(str(data['id']), str(user.pk))
        self.assertEqual(data['email'], user.email)
        self.assertEqual(data['first_name'], user.first_name)
        self.assertEqual(data['last_name'], user.last_name)
        self.assertEqual(data['role'], membership.role)
        self.assertEqual(str(data['membership_id']), str(membership.pk))
        self.assertTrue(data['is_active'])
        self.assertEqual(data['tenant_schema'], self.tenant.schema_name)
        self.assertTrue(data['tenant_slug'])
        self.assertEqual(data['school_name'], 'Auth School')

    def test_unauthenticated_is_401(self):
        response = self.api.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_without_slug_is_401(self):
        bare = APIClient()
        response = bare.get(ME_URL)
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_each_school_role_can_read_me(self):
        cases = (
            (self.admin, self.admin_membership),
            (self.teacher, self.teacher_membership),
            (self.bursar, self.bursar_membership),
            (self.parent, self.parent_membership),
        )
        for user, membership in cases:
            with self.subTest(role=membership.role):
                response = self._as(user).get(ME_URL)
                self.assertEqual(
                    response.status_code, status.HTTP_200_OK, response.data
                )
                self._assert_school_me(
                    response.data, user=user, membership=membership
                )

    def test_inactive_membership_is_403(self):
        inactive = User.objects.create_user(
            email='inactive-me@example.com',
            password='pass12345',
            first_name='Ina',
            last_name='Ctive',
        )
        SchoolMembership.objects.create(
            user=inactive,
            role=SchoolMembership.Role.TEACHER,
            is_active=False,
        )
        response = self._as(inactive).get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data['detail'],
            'Active membership at this school is required.',
        )

    def test_no_membership_on_tenant_is_403(self):
        stranger = User.objects.create_user(
            email='stranger-me@example.com',
            password='pass12345',
        )
        response = self._as(stranger).get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_jwt_selects_tenant_without_header(self):
        token = AccessToken.for_user(self.teacher)
        token['tenant_schema'] = self.tenant.schema_name
        token['role'] = 'teacher'
        token['school_id'] = None
        client = APIClient()
        response = client.get(
            ME_URL,
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self._assert_school_me(
            response.data,
            user=self.teacher,
            membership=self.teacher_membership,
        )

    def test_platform_admin_me_on_public_schema(self):
        operator = User.objects.create_user(
            email='operator-me@platform.example',
            password='pass12345',
            first_name='Op',
            last_name='Erator',
            is_platform_admin=True,
        )
        public = APIClient()
        public.force_authenticate(user=operator)
        response = public.get(ME_URL)
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(str(response.data['id']), str(operator.pk))
        self.assertEqual(response.data['email'], operator.email)
        self.assertEqual(response.data['first_name'], 'Op')
        self.assertEqual(response.data['last_name'], 'Erator')
        self.assertEqual(response.data['role'], 'platform_admin')
        self.assertIsNone(response.data['membership_id'])
        self.assertTrue(response.data['is_active'])
        self.assertEqual(response.data['tenant_schema'], get_public_schema_name())
        self.assertIsNone(response.data['tenant_slug'])
        self.assertIsNone(response.data['school_name'])

    def test_platform_admin_without_membership_is_403_on_tenant(self):
        operator = User.objects.create_user(
            email='operator-tenant-me@platform.example',
            password='pass12345',
            is_platform_admin=True,
        )
        response = self._as(operator).get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_includes_me_profile(self):
        self.api.force_authenticate(user=None)
        response = self.api.post(
            LOGIN_URL,
            {'email': 'teacher-me@example.com', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['role'], 'teacher')
        self._assert_school_me(
            response.data['me'],
            user=self.teacher,
            membership=self.teacher_membership,
        )
