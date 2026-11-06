"""API tests for the staff directory and invite inbox."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from memberships.models import SchoolMembership, StaffInvite
from platform_admin.testing import set_tenant_slug

User = get_user_model()

MEMBERS_URL = '/api/memberships/members/'
INVITES_URL = '/api/memberships/invites/'
ACCEPT_URL = '/api/memberships/invites/accept/'


class StaffDirectoryAndInviteInboxTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Directory School'
        return tenant

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='admin-dir@example.com',
            password='pass12345',
            first_name='Ada',
            last_name='Admin',
        )
        self.teacher = User.objects.create_user(
            email='teacher-dir@example.com',
            password='pass12345',
            first_name='Tunde',
            last_name='Teacher',
        )
        self.bursar = User.objects.create_user(
            email='bursar-dir@example.com',
            password='pass12345',
            first_name='Bisi',
            last_name='Bursar',
        )
        self.parent = User.objects.create_user(
            email='parent-dir@example.com',
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
        SchoolMembership.objects.create(
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

    def test_admin_list_excludes_parents_by_default(self):
        response = self._as(self.admin).get(MEMBERS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        emails = {row['email'] for row in response.data}
        self.assertEqual(
            emails,
            {
                'admin-dir@example.com',
                'teacher-dir@example.com',
                'bursar-dir@example.com',
            },
        )
        self.assertNotIn('parent-dir@example.com', emails)
        teacher_row = next(
            row for row in response.data if row['email'] == 'teacher-dir@example.com'
        )
        self.assertEqual(teacher_row['user'], str(self.teacher.pk))
        self.assertEqual(teacher_row['first_name'], 'Tunde')
        self.assertEqual(teacher_row['role'], SchoolMembership.Role.TEACHER)
        self.assertTrue(teacher_row['is_active'])
        self.assertIn('joined_at', teacher_row)

    def test_role_filter_can_list_parents(self):
        response = self._as(self.admin).get(MEMBERS_URL, {'role': 'parent'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        emails = {row['email'] for row in response.data}
        self.assertEqual(emails, {'parent-dir@example.com'})

    def test_non_admin_cannot_list_or_patch_members(self):
        for user in (self.teacher, self.bursar, self.parent):
            listed = self._as(user).get(MEMBERS_URL)
            self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN, user.email)
            patched = self._as(user).patch(
                f'{MEMBERS_URL}{self.teacher_membership.pk}/',
                {'is_active': False},
                format='json',
            )
            self.assertEqual(patched.status_code, status.HTTP_403_FORBIDDEN, user.email)

    def test_create_membership_via_api_is_not_allowed(self):
        extra = User.objects.create_user(
            email='sneaky@example.com',
            password='pass12345',
        )
        response = self._as(self.admin).post(
            MEMBERS_URL,
            {'user': str(extra.pk), 'role': 'teacher'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_admin_can_change_role_and_soft_deactivate(self):
        detail = f'{MEMBERS_URL}{self.teacher_membership.pk}/'
        patched = self._as(self.admin).patch(
            detail,
            {'role': SchoolMembership.Role.BURSAR},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertEqual(patched.data['role'], SchoolMembership.Role.BURSAR)

        deleted = self._as(self.admin).delete(detail)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.teacher_membership.refresh_from_db()
        self.assertFalse(self.teacher_membership.is_active)
        self.assertTrue(User.objects.filter(pk=self.teacher.pk).exists())

        revived = self._as(self.admin).patch(
            detail,
            {'is_active': True, 'role': SchoolMembership.Role.TEACHER},
            format='json',
        )
        self.assertEqual(revived.status_code, status.HTTP_200_OK, revived.data)
        self.assertTrue(revived.data['is_active'])
        self.assertEqual(revived.data['role'], SchoolMembership.Role.TEACHER)

    def test_last_active_admin_cannot_be_removed(self):
        detail = f'{MEMBERS_URL}{self.admin_membership.pk}/'
        deactivated = self._as(self.admin).patch(
            detail,
            {'is_active': False},
            format='json',
        )
        self.assertEqual(deactivated.status_code, status.HTTP_400_BAD_REQUEST)
        demoted = self._as(self.admin).patch(
            detail,
            {'role': SchoolMembership.Role.TEACHER},
            format='json',
        )
        self.assertEqual(demoted.status_code, status.HTTP_400_BAD_REQUEST)
        deleted = self._as(self.admin).delete(detail)
        self.assertEqual(deleted.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin_membership.refresh_from_db()
        self.assertTrue(self.admin_membership.is_active)
        self.assertEqual(self.admin_membership.role, SchoolMembership.Role.ADMIN)

    def test_second_admin_can_deactivate_the_other(self):
        other = User.objects.create_user(
            email='admin-two@example.com',
            password='pass12345',
        )
        other_membership = SchoolMembership.objects.create(
            user=other,
            role=SchoolMembership.Role.ADMIN,
            is_active=True,
        )
        response = self._as(self.admin).delete(
            f'{MEMBERS_URL}{other_membership.pk}/',
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        other_membership.refresh_from_db()
        self.assertFalse(other_membership.is_active)

    def test_create_invite_omits_token_and_list_is_pending_only(self):
        created = self._as(self.admin).post(
            INVITES_URL,
            {'email': 'new.teacher@example.com', 'role': 'teacher'},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data['status'], StaffInvite.Status.PENDING)
        self.assertNotIn('token', created.data)
        self.assertIn('accept_url', created.data)
        invite_id = created.data['id']

        StaffInvite.objects.create(
            email='already.accepted@example.com',
            role=StaffInvite.Role.BURSAR,
            invited_by=self.admin,
            status=StaffInvite.Status.ACCEPTED,
        )

        listed = self._as(self.admin).get(INVITES_URL)
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        emails = {row['email'] for row in listed.data}
        self.assertEqual(emails, {'new.teacher@example.com'})
        self.assertTrue(all('token' not in row for row in listed.data))
        self.assertTrue(all('accept_url' not in row for row in listed.data))

        retrieved = self._as(self.admin).get(f'{INVITES_URL}{invite_id}/')
        self.assertEqual(retrieved.status_code, status.HTTP_200_OK, retrieved.data)
        self.assertNotIn('token', retrieved.data)

    def test_revoke_pending_invite_blocks_accept(self):
        invite = StaffInvite.objects.create(
            email='revoke.me@example.com',
            role=StaffInvite.Role.TEACHER,
            invited_by=self.admin,
        )
        token = invite.token
        revoked = self._as(self.admin).delete(f'{INVITES_URL}{invite.pk}/')
        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)
        invite.refresh_from_db()
        self.assertEqual(invite.status, StaffInvite.Status.EXPIRED)

        accepted = self.api.post(
            ACCEPT_URL,
            {
                'token': token,
                'password': 'A-reasonably-long-pass-123',
                'first_name': 'Revoked',
                'last_name': 'Invite',
            },
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            SchoolMembership.objects.filter(user__email='revoke.me@example.com').exists()
        )

    def test_cannot_revoke_accepted_invite(self):
        invite = StaffInvite.objects.create(
            email='used@example.com',
            role=StaffInvite.Role.TEACHER,
            invited_by=self.admin,
            status=StaffInvite.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )
        response = self._as(self.admin).delete(f'{INVITES_URL}{invite.pk}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_marks_time_expired_pending_invites(self):
        invite = StaffInvite.objects.create(
            email='stale@example.com',
            role=StaffInvite.Role.TEACHER,
            invited_by=self.admin,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        listed = self._as(self.admin).get(INVITES_URL)
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        self.assertEqual(listed.data, [])
        invite.refresh_from_db()
        self.assertEqual(invite.status, StaffInvite.Status.EXPIRED)

    def test_non_admin_cannot_list_or_create_invites(self):
        listed = self._as(self.teacher).get(INVITES_URL)
        self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN)
        created = self._as(self.teacher).post(
            INVITES_URL,
            {'email': 'nope@example.com', 'role': 'teacher'},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)
