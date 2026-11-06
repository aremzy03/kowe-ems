"""
Header / JWT tenant resolution (Phase 0.1).

Host is not used to select a schema. Spec verification: an authenticated
endpoint succeeds only with a valid JWT for that tenant — missing
identification and a malformed slug must fail.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.template import RequestContext, Template
from django.test import RequestFactory
from django.test.utils import override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from memberships.models import SchoolMembership
from platform_admin.middleware import HeaderTenantMiddleware
from platform_admin.tenancy import frontend_origin_for_tenant, tenant_slug_for
from platform_admin.testing import set_tenant_slug

User = get_user_model()

LOGIN_URL = '/api/auth/login/'
ME_MEMBERSHIP_PROBE = '/api/memberships/invites/'
PARENT_SIGNUP_URL = '/api/memberships/parents/signup/'
REVENUE_URL = '/api/platform/revenue/'
WEBHOOK_URL = '/api/webhooks/paystack/'


class HeaderTenantResolutionTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Resolution School'
        return tenant

    def setUp(self):
        super().setUp()
        cache.clear()
        connection.set_tenant(self.tenant)
        self.teacher = User.objects.create_user(
            email='teacher-res@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(
            user=self.teacher,
            role=SchoolMembership.Role.TEACHER,
            is_active=True,
        )
        self.api = APIClient()

    def _access_for(self, user, schema_name=None):
        token = AccessToken.for_user(user)
        token['tenant_schema'] = schema_name or self.tenant.schema_name
        token['role'] = 'teacher'
        token['school_id'] = None
        return str(token)

    def test_valid_jwt_selects_tenant_without_header(self):
        access = self._access_for(self.teacher)
        response = self.api.get(
            ME_MEMBERSHIP_PROBE,
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        connection.set_tenant(self.tenant)
        # Teacher is not admin: 403 means schema+auth resolved (not 400).
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_endpoint_without_header_or_claim_is_400(self):
        response = self.api.get(ME_MEMBERSHIP_PROBE)
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['detail'], 'Tenant identification required')

    def test_malformed_tenant_slug_is_400(self):
        response = self.api.get(
            ME_MEMBERSHIP_PROBE,
            HTTP_X_TENANT_SLUG='not a valid slug!!!',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['detail'], 'Unknown tenant.')

    def test_jwt_without_tenant_schema_claim_is_401(self):
        token = AccessToken.for_user(self.teacher)
        token['school_id'] = None
        response = self.api.get(
            ME_MEMBERSHIP_PROBE,
            HTTP_AUTHORIZATION=f'Bearer {str(token)}',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['detail'], 'Invalid tenant claim in token.')

    def test_jwt_unknown_schema_claim_is_401(self):
        access = self._access_for(self.teacher, schema_name='does_not_exist')
        response = self.api.get(
            ME_MEMBERSHIP_PROBE,
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_embeds_tenant_schema_claim(self):
        set_tenant_slug(self.api, self.tenant)
        response = self.api.post(
            LOGIN_URL,
            {'email': 'teacher-res@example.com', 'password': 'pass12345'},
            format='json',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('access', response.data)
        access = AccessToken(response.data['access'])
        self.assertEqual(access['tenant_schema'], self.tenant.schema_name)
        self.assertEqual(access['role'], 'teacher')

    def test_pre_auth_login_uses_x_tenant_slug(self):
        set_tenant_slug(self.api, self.tenant)
        response = self.api.post(
            LOGIN_URL,
            {'email': 'teacher-res@example.com', 'password': 'pass12345'},
            format='json',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data['requires_2fa'])

    def test_login_without_slug_on_public_schema_rejects_school_user(self):
        response = self.api.post(
            LOGIN_URL,
            {'email': 'teacher-res@example.com', 'password': 'pass12345'},
            format='json',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_takes_precedence_over_malformed_header(self):
        access = self._access_for(self.teacher)
        response = self.api.get(
            ME_MEMBERSHIP_PROBE,
            HTTP_AUTHORIZATION=f'Bearer {access}',
            HTTP_X_TENANT_SLUG='bogus-unknown-tenant',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_host_header_does_not_select_tenant(self):
        response = self.api.get(
            ME_MEMBERSHIP_PROBE,
            HTTP_HOST=self.domain.domain,
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_slug_matches_domain_first_label(self):
        slug = tenant_slug_for(self.tenant)
        response = self.api.post(
            LOGIN_URL,
            {'email': 'teacher-res@example.com', 'password': 'pass12345'},
            format='json',
            HTTP_X_TENANT_SLUG=slug,
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_invite_url_points_at_frontend_subdomain(self):
        origin = frontend_origin_for_tenant(self.tenant)
        self.assertIn(tenant_slug_for(self.tenant), origin)
        self.assertIn('3000', origin)

    def test_parent_signup_uses_x_tenant_slug(self):
        set_tenant_slug(self.api, self.tenant)
        response = self.api.post(
            PARENT_SIGNUP_URL,
            {
                'email': 'parent-res@example.com',
                'password': 'ParentPass123!',
                'first_name': 'Pat',
                'last_name': 'Ent',
            },
            format='json',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['membership']['role'], 'parent')
        self.assertTrue(
            SchoolMembership.objects.filter(
                user__email='parent-res@example.com',
                role=SchoolMembership.Role.PARENT,
            ).exists()
        )

    def test_options_preflight_does_not_require_tenant(self):
        response = self.api.options(ME_MEMBERSHIP_PROBE)
        connection.set_tenant(self.tenant)
        self.assertNotEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_schema_requests_expose_schema_name(self):
        """Admin's is_public_schema tag reads request.tenant.schema_name."""
        public = get_public_schema_name()
        options = self._public_schema_flag(RequestFactory().options(ME_MEMBERSHIP_PROBE))
        self.assertEqual(options, 'True')

        token = AccessToken.for_user(self.teacher)
        token['tenant_schema'] = public
        public_jwt = RequestFactory().get(
            '/admin/',
            HTTP_AUTHORIZATION=f'Bearer {str(token)}',
        )
        self.assertEqual(self._public_schema_flag(public_jwt), 'True')

        school = RequestFactory().get(
            ME_MEMBERSHIP_PROBE,
            HTTP_AUTHORIZATION=f'Bearer {self._access_for(self.teacher)}',
        )
        self.assertEqual(self._public_schema_flag(school), 'False')

    def _public_schema_flag(self, request):
        def get_response(req):
            rendered = Template(
                '{% load tenant %}{% is_public_schema as is_public %}{{ is_public }}'
            ).render(RequestContext(req))
            return HttpResponse(rendered)

        try:
            response = HeaderTenantMiddleware(get_response)(request)
        finally:
            connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()


class PublicPathAndCorsTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'CORS School'
        return tenant

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.client = APIClient()

    def test_webhook_path_does_not_require_tenant_header(self):
        response = self.client.post(
            WEBHOOK_URL,
            data=b'{}',
            content_type='application/json',
        )
        connection.set_tenant(self.tenant)
        # HMAC fails closed (401) rather than tenant-identification 400.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_path_does_not_require_tenant_header(self):
        response = self.client.get(REVENUE_URL)
        connection.set_tenant(self.tenant)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_admin_path_does_not_require_tenant_header(self):
        index = self.client.get('/admin/')
        connection.set_tenant(self.tenant)
        self.assertEqual(index.status_code, status.HTTP_302_FOUND)
        self.assertIn('/admin/login/', index.url)
        self.assertNotIn(
            'Tenant identification required',
            index.content.decode(),
        )

        login = self.client.get('/admin/login/')
        connection.set_tenant(self.tenant)
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            'Tenant identification required',
            login.content.decode(),
        )

        # No trailing slash must stay public so APPEND_SLASH can redirect.
        bare = self.client.get('/admin')
        connection.set_tenant(self.tenant)
        self.assertNotEqual(bare.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(
            'Tenant identification required',
            bare.content.decode(),
        )

    def test_admin_index_renders_for_staff_without_tenant_header(self):
        staff = User.objects.create_superuser(
            email='staff-admin@example.com',
            password='pass12345',
        )
        self.client.force_login(staff)
        index = self.client.get('/admin/')
        connection.set_tenant(self.tenant)
        self.assertEqual(index.status_code, status.HTTP_200_OK)
        self.assertNotIn('AttributeError', index.content.decode())

    def test_admin_index_still_requires_staff(self):
        member = User.objects.create_user(
            email='not-staff@example.com',
            password='pass12345',
        )
        self.client.force_login(member)
        index = self.client.get('/admin/')
        connection.set_tenant(self.tenant)
        self.assertEqual(index.status_code, status.HTTP_302_FOUND)
        self.assertIn('/admin/login/', index.url)

    def test_cors_allows_school_subdomain_origin(self):
        overrides = override_settings(
            CORS_ALLOW_ALL_ORIGINS=False,
            CORS_ALLOWED_ORIGINS=[],
            CORS_ALLOWED_ORIGIN_REGEXES=[r'^https://[\w-]+\.yourapp\.com$'],
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        origin = 'https://schoolb.yourapp.com'
        response = self.client.options(
            LOGIN_URL,
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type,x-tenant-slug',
        )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Access-Control-Allow-Origin'), origin)
        allow_headers = (response.get('Access-Control-Allow-Headers') or '').lower()
        self.assertIn('x-tenant-slug', allow_headers)

    def test_cors_rejects_unlisted_origin(self):
        overrides = override_settings(
            CORS_ALLOW_ALL_ORIGINS=False,
            CORS_ALLOWED_ORIGINS=[],
            CORS_ALLOWED_ORIGIN_REGEXES=[r'^https://[\w-]+\.yourapp\.com$'],
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        response = self.client.options(
            LOGIN_URL,
            HTTP_ORIGIN='https://evil.example',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        connection.set_tenant(self.tenant)
        self.assertNotEqual(
            response.get('Access-Control-Allow-Origin'),
            'https://evil.example',
        )
