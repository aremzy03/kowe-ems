"""
Idempotency + permission tests for daily attendance bulk upsert.

Mirrors Phase 2 score-entry behaviour: identical retry must not grow
DailyAttendance or AttendanceAuditLog rows.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from academics.models import (
    Arm,
    ClassLevel,
    ClassTeacherAssignment,
    Enrollment,
    Session,
    Student,
    Term,
)
from assessment.report_cards import get_attendance_summary_for_report
from attendance.models import AttendanceAuditLog, DailyAttendance
from attendance.services import (
    compute_term_attendance_summary,
    upsert_daily_attendance,
)
from memberships.models import SchoolMembership
from platform_admin.testing import set_tenant_slug

User = get_user_model()


class DailyAttendanceIdempotencyTests(TenantTestCase):
    """Service + API idempotency for bulk attendance entry."""

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Attendance Test School'
        return tenant

    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            name='2026/2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.term = Term.objects.create(
            session=self.session,
            name=Term.Name.FIRST,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15),
            is_active=True,
        )
        self.class_level = ClassLevel.objects.create(name='JSS1')
        self.arm = Arm.objects.create(name='A', class_level=self.class_level)
        self.attendance_date = date(2026, 9, 10)

        self.admin = User.objects.create_user(
            email='admin-att@example.com',
            password='pass12345',
        )
        self.teacher = User.objects.create_user(
            email='teacher-att@example.com',
            password='pass12345',
        )
        self.other_teacher = User.objects.create_user(
            email='other-teacher-att@example.com',
            password='pass12345',
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
            user=self.other_teacher,
            role=SchoolMembership.Role.TEACHER,
            is_active=True,
        )

        ClassTeacherAssignment.objects.create(
            teacher=self.teacher,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
        )

        self.student = Student.objects.create(
            first_name='Ada',
            last_name='Okeke',
            admission_number='ATT-001',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2014, 3, 1),
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )

        self.client = APIClient()
        self.api = self.client
        set_tenant_slug(self.api, self.tenant)

    def _bulk_payload(self, status_value='present', remarks=''):
        return {
            'class_level_id': str(self.class_level.id),
            'arm_id': str(self.arm.id),
            'term_id': str(self.term.id),
            'date': self.attendance_date.isoformat(),
            'entries': [
                {
                    'student_id': str(self.student.id),
                    'status': status_value,
                    'remarks': remarks,
                }
            ],
        }

    def test_upsert_service_idempotent_no_duplicate_or_audit_churn(self):
        obj1, created1, changed1 = upsert_daily_attendance(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=self.attendance_date,
            status=DailyAttendance.Status.ABSENT,
            marked_by=self.teacher,
            remarks='sick',
        )
        self.assertTrue(created1)
        self.assertTrue(changed1)
        self.assertEqual(DailyAttendance.objects.count(), 1)
        self.assertEqual(AttendanceAuditLog.objects.count(), 1)

        obj2, created2, changed2 = upsert_daily_attendance(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=self.attendance_date,
            status=DailyAttendance.Status.ABSENT,
            marked_by=self.teacher,
            remarks='sick',
        )
        self.assertEqual(obj1.pk, obj2.pk)
        self.assertFalse(created2)
        self.assertFalse(changed2)
        self.assertEqual(DailyAttendance.objects.count(), 1)
        self.assertEqual(AttendanceAuditLog.objects.count(), 1)

    def test_status_correction_writes_second_audit_row(self):
        upsert_daily_attendance(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=self.attendance_date,
            status=DailyAttendance.Status.ABSENT,
            marked_by=self.teacher,
        )
        upsert_daily_attendance(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=self.attendance_date,
            status=DailyAttendance.Status.PRESENT,
            marked_by=self.teacher,
        )
        self.assertEqual(DailyAttendance.objects.count(), 1)
        self.assertEqual(AttendanceAuditLog.objects.count(), 2)
        latest = AttendanceAuditLog.objects.order_by('-timestamp').first()
        self.assertEqual(latest.old_status, DailyAttendance.Status.ABSENT)
        self.assertEqual(latest.new_status, DailyAttendance.Status.PRESENT)

    def test_bulk_upsert_api_idempotent_retry(self):
        self.api.force_authenticate(user=self.teacher)
        url = '/api/attendance/daily/bulk-upsert/'
        payload = self._bulk_payload(status_value='late', remarks='bus')

        first = self.api.post(url, payload, format='json')
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertEqual(first.data['succeeded'], 1)
        self.assertTrue(first.data['results'][0]['created'])
        self.assertEqual(DailyAttendance.objects.count(), 1)
        self.assertEqual(AttendanceAuditLog.objects.count(), 1)

        second = self.api.post(url, payload, format='json')
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(second.data['succeeded'], 1)
        self.assertFalse(second.data['results'][0]['created'])
        self.assertFalse(second.data['results'][0]['changed'])
        self.assertEqual(DailyAttendance.objects.count(), 1)
        self.assertEqual(AttendanceAuditLog.objects.count(), 1)

    def test_unassigned_teacher_bulk_upsert_denied(self):
        self.api.force_authenticate(user=self.other_teacher)
        url = '/api/attendance/daily/bulk-upsert/'
        response = self.api.post(
            url,
            self._bulk_payload(status_value='present'),
            format='json',
        )
        # Per-entry failure → 400 when none succeed
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['succeeded'], 0)
        self.assertEqual(DailyAttendance.objects.count(), 0)

    def test_date_outside_term_rejected(self):
        self.api.force_authenticate(user=self.teacher)
        payload = self._bulk_payload()
        payload['date'] = (self.term.end_date + timedelta(days=3)).isoformat()
        response = self.api.post(
            '/api/attendance/daily/bulk-upsert/',
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(DailyAttendance.objects.count(), 0)


class TermAttendanceSummaryTests(TenantTestCase):
    """Compute-on-read summary + register grid (Prompt 3)."""

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Attendance Summary School'
        return tenant

    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            name='2026/2027-S',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.term = Term.objects.create(
            session=self.session,
            name=Term.Name.FIRST,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15),
            is_active=True,
            total_school_days=60,
        )
        self.class_level = ClassLevel.objects.create(name='JSS2')
        self.arm = Arm.objects.create(name='B', class_level=self.class_level)

        self.admin = User.objects.create_user(
            email='admin-sum@example.com',
            password='pass12345',
        )
        self.teacher = User.objects.create_user(
            email='teacher-sum@example.com',
            password='pass12345',
        )
        self.other_teacher = User.objects.create_user(
            email='other-sum@example.com',
            password='pass12345',
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
            user=self.other_teacher,
            role=SchoolMembership.Role.TEACHER,
            is_active=True,
        )
        ClassTeacherAssignment.objects.create(
            teacher=self.teacher,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
        )
        self.student = Student.objects.create(
            first_name='Chidi',
            last_name='Eze',
            admission_number='SUM-001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2013, 5, 1),
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )
        self.client = APIClient()
        self.api = self.client
        set_tenant_slug(self.api, self.tenant)

    def _mark(self, day, status_value):
        upsert_daily_attendance(
            student=self.student,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=day,
            status=status_value,
            marked_by=self.teacher,
        )

    def test_summary_unavailable_with_zero_marks(self):
        summary = compute_term_attendance_summary(
            student=self.student,
            term=self.term,
        )
        self.assertFalse(summary.available)
        self.assertEqual(summary.days_marked, 0)
        self.assertIsNone(summary.attendance_percentage)

        placeholder = get_attendance_summary_for_report(
            student=self.student,
            term=self.term,
        )
        self.assertFalse(placeholder.available)

    def test_summary_percentage_present_over_total_school_days(self):
        # 3 present, 1 late, 1 absent → % = 3/60 = 5.00 (late not in numerator)
        self._mark(date(2026, 9, 7), DailyAttendance.Status.PRESENT)  # Mon
        self._mark(date(2026, 9, 8), DailyAttendance.Status.PRESENT)
        self._mark(date(2026, 9, 9), DailyAttendance.Status.PRESENT)
        self._mark(date(2026, 9, 10), DailyAttendance.Status.LATE)
        self._mark(date(2026, 9, 11), DailyAttendance.Status.ABSENT)

        summary = compute_term_attendance_summary(
            student=self.student,
            term=self.term,
        )
        self.assertTrue(summary.available)
        self.assertEqual(summary.days_present, 3)
        self.assertEqual(summary.days_late, 1)
        self.assertEqual(summary.days_absent, 1)
        self.assertEqual(summary.total_school_days, 60)
        self.assertEqual(summary.attendance_percentage, Decimal('5.00'))

        placeholder = get_attendance_summary_for_report(
            student=self.student,
            term=self.term,
        )
        self.assertTrue(placeholder.available)
        self.assertEqual(placeholder.days_present, 3)
        self.assertEqual(placeholder.attendance_percentage, '5.00')

    def test_summary_api_as_class_teacher(self):
        self._mark(date(2026, 9, 7), DailyAttendance.Status.PRESENT)
        self.api.force_authenticate(user=self.teacher)
        url = (
            f'/api/attendance/summaries/student/'
            f'?student={self.student.id}&term={self.term.id}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['available'])
        self.assertEqual(response.data['days_present'], 1)

    def test_summary_api_denied_for_unassigned_teacher(self):
        self.api.force_authenticate(user=self.other_teacher)
        url = (
            f'/api/attendance/summaries/student/'
            f'?student={self.student.id}&term={self.term.id}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_grid_month_view(self):
        self._mark(date(2026, 9, 7), DailyAttendance.Status.PRESENT)
        self._mark(date(2026, 9, 8), DailyAttendance.Status.ABSENT)
        self.api.force_authenticate(user=self.teacher)
        url = (
            f'/api/attendance/register/'
            f'?class_level={self.class_level.id}'
            f'&arm={self.arm.id}'
            f'&term={self.term.id}'
            f'&month=2026-09'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('2026-09-07', response.data['dates'])
        # Weekend 2026-09-05 (Sat) must not appear
        self.assertNotIn('2026-09-05', response.data['dates'])
        self.assertEqual(len(response.data['students']), 1)
        cells_by_date = {
            c['date']: c['status'] for c in response.data['grid'][0]['cells']
        }
        self.assertEqual(cells_by_date['2026-09-07'], 'present')
        self.assertEqual(cells_by_date['2026-09-08'], 'absent')
        self.assertIsNone(cells_by_date.get('2026-09-09'))


class ParentAndAdminAttendanceAccessTests(TenantTestCase):
    """Prompt 5: parent linked-student reads + admin school overview."""

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Attendance Access School'
        return tenant

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        from academics.models import Guardian, StudentGuardianLink

        self.session = Session.objects.create(
            name='2026/2027-P5',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.term = Term.objects.create(
            session=self.session,
            name=Term.Name.FIRST,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15),
            is_active=True,
            total_school_days=60,
        )
        self.class_level = ClassLevel.objects.create(name='JSS3')
        self.arm = Arm.objects.create(name='C', class_level=self.class_level)
        self.other_class = ClassLevel.objects.create(name='JSS3-Other')
        self.other_arm = Arm.objects.create(
            name='D',
            class_level=self.other_class,
        )

        self.admin = User.objects.create_user(
            email='admin-p5@example.com',
            password='pass12345',
        )
        self.teacher = User.objects.create_user(
            email='teacher-p5@example.com',
            password='pass12345',
        )
        self.parent = User.objects.create_user(
            email='parent-p5@example.com',
            password='pass12345',
        )
        self.other_parent = User.objects.create_user(
            email='other-parent-p5@example.com',
            password='pass12345',
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
        SchoolMembership.objects.create(
            user=self.other_parent,
            role=SchoolMembership.Role.PARENT,
            is_active=True,
        )
        # IsSchoolAdmin requires confirmed TOTP (shared User / public schema).
        TOTPDevice.objects.create(
            user=self.admin,
            name='test',
            confirmed=True,
        )

        ClassTeacherAssignment.objects.create(
            teacher=self.teacher,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
        )

        self.child = Student.objects.create(
            first_name='Amaka',
            last_name='Okafor',
            admission_number='P5-001',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2014, 3, 1),
            admission_date=date(2026, 9, 1),
        )
        self.unrelated = Student.objects.create(
            first_name='Bola',
            last_name='Ade',
            admission_number='P5-002',
            gender=Student.Gender.MALE,
            date_of_birth=date(2014, 4, 1),
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=self.child,
            class_level=self.class_level,
            arm=self.arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )
        Enrollment.objects.create(
            student=self.unrelated,
            class_level=self.other_class,
            arm=self.other_arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )

        guardian = Guardian.objects.create(
            user=self.parent,
            full_name='Parent P5',
            relationship_to_student=Guardian.Relationship.MOTHER,
        )
        StudentGuardianLink.objects.create(
            student=self.child,
            guardian=guardian,
            is_primary_contact=True,
        )
        # other_parent has membership but no StudentGuardianLink

        self.attendance_date = date(2026, 9, 10)
        upsert_daily_attendance(
            student=self.child,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=self.attendance_date,
            status=DailyAttendance.Status.PRESENT,
            marked_by=self.teacher,
        )
        upsert_daily_attendance(
            student=self.child,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
            attendance_date=date(2026, 9, 11),
            status=DailyAttendance.Status.ABSENT,
            marked_by=self.teacher,
        )

        self.client = APIClient()
        self.api = self.client
        set_tenant_slug(self.api, self.tenant)

    def test_parent_summary_for_linked_child(self):
        self.api.force_authenticate(user=self.parent)
        url = (
            f'/api/attendance/summaries/student/'
            f'?student={self.child.id}&term={self.term.id}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['available'])
        self.assertEqual(response.data['days_present'], 1)
        self.assertEqual(response.data['days_absent'], 1)

    def test_parent_summary_denied_for_unlinked_student(self):
        self.api.force_authenticate(user=self.parent)
        url = (
            f'/api/attendance/summaries/student/'
            f'?student={self.unrelated.id}&term={self.term.id}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_without_link_denied(self):
        self.api.force_authenticate(user=self.other_parent)
        url = (
            f'/api/attendance/summaries/student/'
            f'?student={self.child.id}&term={self.term.id}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_daily_log_for_linked_child(self):
        self.api.force_authenticate(user=self.parent)
        url = (
            f'/api/attendance/parents/daily/'
            f'?student={self.child.id}&term={self.term.id}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['count'], 2)
        statuses = {row['status'] for row in response.data['results']}
        self.assertEqual(statuses, {'present', 'absent'})

    def test_parent_daily_log_denied_for_unlinked(self):
        self.api.force_authenticate(user=self.parent)
        url = f'/api/attendance/parents/daily/?student={self.unrelated.id}'
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_overview_by_date_pending_and_complete(self):
        self.api.force_authenticate(user=self.admin)
        url = (
            f'/api/attendance/admin/overview/'
            f'?date={self.attendance_date.isoformat()}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['mode'], 'date')
        by_arm = {c['arm_id']: c for c in response.data['classes']}
        marked_class = by_arm[str(self.arm.id)]
        pending_class = by_arm[str(self.other_arm.id)]
        self.assertEqual(marked_class['status'], 'complete')
        self.assertEqual(marked_class['marked_count'], 1)
        self.assertEqual(pending_class['status'], 'pending')
        self.assertEqual(pending_class['marked_count'], 0)
        self.assertGreaterEqual(response.data['summary']['complete'], 1)
        self.assertGreaterEqual(response.data['summary']['pending'], 1)

    def test_admin_overview_by_term(self):
        self.api.force_authenticate(user=self.admin)
        url = f'/api/attendance/admin/overview/?term={self.term.id}'
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['mode'], 'term')
        by_arm = {c['arm_id']: c for c in response.data['classes']}
        self.assertEqual(by_arm[str(self.arm.id)]['days_with_marks'], 2)
        self.assertTrue(by_arm[str(self.other_arm.id)]['never_marked'])

    def test_teacher_cannot_access_admin_overview(self):
        self.api.force_authenticate(user=self.teacher)
        url = (
            f'/api/attendance/admin/overview/'
            f'?date={self.attendance_date.isoformat()}'
        )
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_parent_cannot_access_admin_overview(self):
        self.api.force_authenticate(user=self.parent)
        url = f'/api/attendance/admin/overview/?term={self.term.id}'
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
