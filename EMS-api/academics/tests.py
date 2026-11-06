"""API tests for guardian contacts, student-guardian links, and linking codes."""

from datetime import date

from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from academics.models import (
    Guardian,
    Student,
    StudentGuardianLink,
    StudentLinkingCode,
)
from memberships.models import SchoolMembership
from platform_admin.testing import set_tenant_slug

User = get_user_model()

STUDENTS_URL = '/api/academics/students/'
GUARDIANS_URL = '/api/academics/guardians/'
LINKS_URL = '/api/academics/guardian-links/'
REDEEM_URL = '/api/academics/linking-codes/redeem/'


class GuardianLinkAndCodeTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Guardian School'
        return tenant

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='admin-guard@example.com',
            password='pass12345',
            first_name='Ada',
            last_name='Admin',
        )
        self.teacher = User.objects.create_user(
            email='teacher-guard@example.com',
            password='pass12345',
        )
        self.parent = User.objects.create_user(
            email='parent-guard@example.com',
            password='pass12345',
            first_name='Pat',
            last_name='Parent',
        )
        SchoolMembership.objects.create(
            user=self.admin,
            role=SchoolMembership.Role.ADMIN,
            is_active=True,
        )
        SchoolMembership.objects.create(
            user=self.teacher,
            role=SchoolMembership.Role.TEACHER,
            is_active=True,
        )
        SchoolMembership.objects.create(
            user=self.parent,
            role=SchoolMembership.Role.PARENT,
            is_active=True,
        )

        self.api = APIClient()
        set_tenant_slug(self.api, self.tenant)

    def _as(self, user):
        self.api.force_authenticate(user=user)
        return self.api

    def _student(self, admission='STU-001', **kwargs):
        defaults = {
            'first_name': 'Ada',
            'last_name': 'Okeke',
            'date_of_birth': date(2014, 3, 1),
            'gender': Student.Gender.FEMALE,
            'admission_number': admission,
            'admission_date': date(2026, 9, 1),
        }
        defaults.update(kwargs)
        return Student.objects.create_with_linking_code(**defaults)

    def _unused_code(self, student):
        return student.linking_codes.filter(is_used=False).order_by('-created_at').first()

    def test_non_admin_cannot_manage_guardians_or_links(self):
        student = self._student()
        guardian = Guardian.objects.create(
            full_name='Chioma Okeke',
            phone_number='+2348011111111',
        )
        link = StudentGuardianLink.objects.create(
            student=student,
            guardian=guardian,
        )
        for user in (self.teacher, self.parent):
            listed = self._as(user).get(GUARDIANS_URL)
            self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN, user.email)
            created = self._as(user).post(
                GUARDIANS_URL,
                {'full_name': 'Nope', 'phone_number': '+2348000000000'},
                format='json',
            )
            self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN, user.email)
            linked = self._as(user).get(LINKS_URL)
            self.assertEqual(linked.status_code, status.HTTP_403_FORBIDDEN, user.email)
            regenerated = self._as(user).post(
                f'{STUDENTS_URL}{student.pk}/regenerate-linking-code/',
                {},
                format='json',
            )
            self.assertEqual(
                regenerated.status_code, status.HTTP_403_FORBIDDEN, user.email
            )
            deleted = self._as(user).delete(f'{LINKS_URL}{link.pk}/')
            self.assertEqual(deleted.status_code, status.HTTP_403_FORBIDDEN, user.email)

    def test_admin_guardian_crud_and_delete_blocked_while_linked(self):
        created = self._as(self.admin).post(
            GUARDIANS_URL,
            {
                'full_name': 'Chioma Okeke',
                'phone_number': '+2348011111111',
                'relationship_to_student': Guardian.Relationship.MOTHER,
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        guardian_id = created.data['id']
        self.assertEqual(created.data['full_name'], 'Chioma Okeke')
        self.assertEqual(created.data['phone_number'], '+2348011111111')
        self.assertIsNone(created.data['user'])
        self.assertIsNone(created.data['user_email'])

        listed = self._as(self.admin).get(GUARDIANS_URL)
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        self.assertEqual(len(listed.data), 1)

        patched = self._as(self.admin).patch(
            f'{GUARDIANS_URL}{guardian_id}/',
            {'phone_number': '+2348099999999'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertEqual(patched.data['phone_number'], '+2348099999999')

        student = self._student()
        linked = self._as(self.admin).post(
            LINKS_URL,
            {
                'student': str(student.pk),
                'guardian': guardian_id,
                'is_primary_contact': True,
            },
            format='json',
        )
        self.assertEqual(linked.status_code, status.HTTP_201_CREATED, linked.data)

        blocked = self._as(self.admin).delete(f'{GUARDIANS_URL}{guardian_id}/')
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT, blocked.data)
        self.assertTrue(Guardian.objects.filter(pk=guardian_id).exists())
        self.assertTrue(
            StudentGuardianLink.objects.filter(pk=linked.data['id']).exists()
        )

        unlinked = self._as(self.admin).delete(f'{LINKS_URL}{linked.data["id"]}/')
        self.assertEqual(unlinked.status_code, status.HTTP_204_NO_CONTENT)
        deleted = self._as(self.admin).delete(f'{GUARDIANS_URL}{guardian_id}/')
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Guardian.objects.filter(pk=guardian_id).exists())

    def test_guardian_create_requires_name_or_phone(self):
        response = self._as(self.admin).post(
            GUARDIANS_URL,
            {'relationship_to_student': Guardian.Relationship.FATHER},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_link_list_filters_by_student_and_rejects_duplicates(self):
        student_a = self._student('STU-A')
        student_b = self._student('STU-B')
        guardian = Guardian.objects.create(
            full_name='Ifeanyi Okeke',
            phone_number='+2348022222222',
        )
        link_a = StudentGuardianLink.objects.create(
            student=student_a,
            guardian=guardian,
            is_primary_contact=True,
        )
        StudentGuardianLink.objects.create(
            student=student_b,
            guardian=guardian,
            is_primary_contact=False,
        )

        filtered = self._as(self.admin).get(LINKS_URL, {'student': str(student_a.pk)})
        self.assertEqual(filtered.status_code, status.HTTP_200_OK, filtered.data)
        self.assertEqual(len(filtered.data), 1)
        self.assertEqual(filtered.data[0]['id'], str(link_a.pk))
        self.assertEqual(filtered.data[0]['guardian_full_name'], 'Ifeanyi Okeke')
        self.assertEqual(filtered.data[0]['guardian_phone_number'], '+2348022222222')

        duplicate = self._as(self.admin).post(
            LINKS_URL,
            {'student': str(student_a.pk), 'guardian': str(guardian.pk)},
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already linked', str(duplicate.data).lower())

    def test_patch_primary_demotes_other_links_for_student(self):
        student = self._student()
        mother = Guardian.objects.create(
            full_name='Mother',
            relationship_to_student=Guardian.Relationship.MOTHER,
            phone_number='+2348033333333',
        )
        father = Guardian.objects.create(
            full_name='Father',
            relationship_to_student=Guardian.Relationship.FATHER,
            phone_number='+2348044444444',
        )
        primary = StudentGuardianLink.objects.create(
            student=student,
            guardian=mother,
            is_primary_contact=True,
        )
        secondary = StudentGuardianLink.objects.create(
            student=student,
            guardian=father,
            is_primary_contact=False,
        )

        patched = self._as(self.admin).patch(
            f'{LINKS_URL}{secondary.pk}/',
            {'is_primary_contact': True},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertTrue(patched.data['is_primary_contact'])
        primary.refresh_from_db()
        secondary.refresh_from_db()
        self.assertFalse(primary.is_primary_contact)
        self.assertTrue(secondary.is_primary_contact)

    def test_student_create_returns_linking_code_and_nested_guardian(self):
        created = self._as(self.admin).post(
            STUDENTS_URL,
            {
                'first_name': 'Tolu',
                'last_name': 'Adeyemi',
                'date_of_birth': '2015-04-12',
                'gender': Student.Gender.FEMALE,
                'admission_number': 'ADM-NEW',
                'admission_date': '2026-09-08',
                'guardian': {
                    'full_name': 'Bola Adeyemi',
                    'phone_number': '+2348055555555',
                    'relationship_to_student': Guardian.Relationship.MOTHER,
                    'is_primary_contact': True,
                },
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertTrue(created.data['linking_code'])
        self.assertEqual(len(created.data['guardian_links']), 1)
        self.assertEqual(
            created.data['guardian_links'][0]['guardian_full_name'],
            'Bola Adeyemi',
        )

        listed = self._as(self.admin).get(STUDENTS_URL)
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        row = next(item for item in listed.data if item['id'] == created.data['id'])
        self.assertEqual(row['linking_code'], created.data['linking_code'])
        self.assertNotIn('guardian_links', row)

        retrieved = self._as(self.admin).get(f'{STUDENTS_URL}{created.data["id"]}/')
        self.assertEqual(retrieved.status_code, status.HTTP_200_OK, retrieved.data)
        self.assertEqual(len(retrieved.data['guardian_links']), 1)

    def test_regenerate_invalidates_unused_code_and_issues_new(self):
        student = self._student()
        old = self._unused_code(student)
        self.assertIsNotNone(old)
        old_code = old.code

        regenerated = self._as(self.admin).post(
            f'{STUDENTS_URL}{student.pk}/regenerate-linking-code/',
            {},
            format='json',
        )
        self.assertEqual(
            regenerated.status_code, status.HTTP_200_OK, regenerated.data
        )
        new_code = regenerated.data['linking_code']
        self.assertTrue(new_code)
        self.assertNotEqual(new_code, old_code)

        old.refresh_from_db()
        self.assertTrue(old.is_used)
        self.assertIsNone(old.used_by_id)
        self.assertIsNotNone(old.used_at)

        unused = StudentLinkingCode.objects.filter(student=student, is_used=False)
        self.assertEqual(unused.count(), 1)
        self.assertEqual(unused.get().code, new_code)

        listed = self._as(self.admin).get(STUDENTS_URL)
        row = next(item for item in listed.data if item['id'] == str(student.pk))
        self.assertEqual(row['linking_code'], new_code)

        rejected = self._as(self.parent).post(
            REDEEM_URL,
            {'code': old_code, 'relationship_to_student': 'mother'},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

        redeemed = self._as(self.parent).post(
            REDEEM_URL,
            {'code': new_code, 'relationship_to_student': 'mother'},
            format='json',
        )
        self.assertEqual(redeemed.status_code, status.HTTP_200_OK, redeemed.data)
        self.assertEqual(redeemed.data['student_id'], str(student.pk))
        self.assertTrue(
            StudentGuardianLink.objects.filter(
                student=student,
                guardian__user=self.parent,
            ).exists()
        )

    def test_regenerate_after_code_is_used(self):
        student = self._student()
        used = self._unused_code(student)
        used.mark_redeemed(self.parent)
        self.assertIsNone(self._unused_code(student))

        listed = self._as(self.admin).get(STUDENTS_URL)
        row = next(item for item in listed.data if item['id'] == str(student.pk))
        self.assertIsNone(row['linking_code'])

        regenerated = self._as(self.admin).post(
            f'{STUDENTS_URL}{student.pk}/regenerate-linking-code/',
            {},
            format='json',
        )
        self.assertEqual(
            regenerated.status_code, status.HTTP_200_OK, regenerated.data
        )
        self.assertTrue(regenerated.data['linking_code'])
        self.assertIsNotNone(self._unused_code(student))
        used.refresh_from_db()
        self.assertEqual(used.used_by_id, self.parent.pk)
