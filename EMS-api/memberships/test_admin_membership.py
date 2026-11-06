"""Public-schema Django admin can attach a user to a school and edit the role."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

from memberships.models import SchoolMembership

User = get_user_model()

LIST_URL = '/admin/memberships/schoolmembership/'
ADD_URL = '/admin/memberships/schoolmembership/add/'


class SchoolMembershipAdminTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Membership School'
        return tenant

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.staff = User.objects.create_superuser(
            email='staff-membership@example.com',
            password='pass12345',
        )
        self.person = User.objects.create_user(
            email='new-teacher@example.com',
            password='pass12345',
        )
        self.existing = User.objects.create_user(
            email='existing-admin@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(
            user=self.existing,
            role=SchoolMembership.Role.ADMIN,
            is_active=True,
        )
        self.http = Client()
        self.http.force_login(self.staff)

    def test_list_shows_membership_from_the_school_schema(self):
        response = self.http.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'existing-admin@example.com')
        self.assertContains(response, 'Admin')

    def test_add_and_change_role_inside_the_school_schema(self):
        added = self.http.post(ADD_URL, {
            'tenant': str(self.tenant.pk),
            'user': str(self.person.pk),
            'role': SchoolMembership.Role.TEACHER,
            'is_active': 'on',
        })
        self.assertEqual(added.status_code, 302)

        with schema_context(self.tenant.schema_name):
            membership = SchoolMembership.objects.get(user_id=self.person.pk)
            self.assertEqual(membership.role, SchoolMembership.Role.TEACHER)
            membership_id = membership.pk

        change_url = (
            f'/admin/memberships/schoolmembership/'
            f'{self.tenant.schema_name}/{membership_id}/change/'
        )
        changed = self.http.post(change_url, {
            'role': SchoolMembership.Role.BURSAR,
            'is_active': 'on',
        })
        self.assertEqual(changed.status_code, 302)

        with schema_context(self.tenant.schema_name):
            membership = SchoolMembership.objects.get(pk=membership_id)
            self.assertEqual(membership.role, SchoolMembership.Role.BURSAR)

    def test_second_membership_for_the_same_user_is_rejected(self):
        response = self.http.post(ADD_URL, {
            'tenant': str(self.tenant.pk),
            'user': str(self.existing.pk),
            'role': SchoolMembership.Role.TEACHER,
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already belongs')
        with schema_context(self.tenant.schema_name):
            self.assertEqual(
                SchoolMembership.objects.filter(user_id=self.existing.pk).count(),
                1,
            )
