"""
Publication gate for term results (Phase 5, Prompt 4).

Before this gate, a linked parent could read TermResultSummary, subject
TermResult scores, and the report-card PDF as soon as recompute had run.
These tests pin the retrofit: parents see nothing score-like until an
admin publishes; admin and teacher reads stay open; publish queues email
and WhatsApp once, on commit.
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from academics.models import (
    Arm,
    ClassLevel,
    ClassSubjectAssignment,
    Enrollment,
    Guardian,
    Session,
    Student,
    StudentGuardianLink,
    Subject,
    Term,
)
from assessment.models import TermResult, TermResultSummary
from assessment.report_cards import build_report_card_context
from assessment.services import recompute_class_term_summaries
from assessment.views import RESULTS_NOT_PUBLISHED_DETAIL
from communications.models import NotificationLog
from communications.whatsapp_schedule import use_memory_schedule
from memberships.models import SchoolMembership
from platform_admin.testing import set_tenant_slug

User = get_user_model()

RESULTS_URL = '/api/assessment/results/student/'
PUBLISH_URL = '/api/assessment/results/publish/'
REPORT_URL = '/api/assessment/report-cards/'
RECOMPUTE_URL = '/api/assessment/results/recompute/'
SCORES_URL = '/api/assessment/scores/'
BROADSHEET_URL = '/api/assessment/broadsheet/'

SCORE_A = Decimal('91.25')
AVERAGE_A = Decimal('88.50')
REMARK_A = 'HIDDEN-REMARK-A'
REMARK_ADMIN_A = 'HIDDEN-ADMIN-A'


class ResultPublicationGateTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Publish School'
        return tenant

    def setUp(self):
        super().setUp()
        use_memory_schedule()
        self.admin = self._make_user('admin-pub', SchoolMembership.Role.ADMIN, totp=True)
        self.admin_no_2fa = self._make_user(
            'admin-pub-plain', SchoolMembership.Role.ADMIN, totp=False,
        )
        self.bursar = self._make_user(
            'bursar-pub', SchoolMembership.Role.BURSAR, totp=True,
        )
        self.teacher = self._make_user('teacher-pub', SchoolMembership.Role.TEACHER)
        self.parent = self._make_user('parent-pub', SchoolMembership.Role.PARENT)
        self.parent_two = self._make_user('parent2-pub', SchoolMembership.Role.PARENT)
        self.parent_other = self._make_user(
            'parent-other-pub', SchoolMembership.Role.PARENT,
        )
        self.unlinked = self._make_user('parent-unlinked-pub', SchoolMembership.Role.PARENT)

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
            end_date=date(2026, 12, 18),
            is_active=True,
        )
        self.class_level = ClassLevel.objects.create(name='JSS1')
        self.other_level = ClassLevel.objects.create(name='JSS2')
        self.arm = Arm.objects.create(class_level=self.class_level, name='A')
        self.other_arm = Arm.objects.create(class_level=self.class_level, name='B')
        self.foreign_arm = Arm.objects.create(class_level=self.other_level, name='A')
        self.subject = Subject.objects.create(name='Mathematics', code='MTH')
        ClassSubjectAssignment.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
        )

        self.student_a = self._enroll('Ada', 'Adebayo', 'ADM-A', self.arm)
        self.student_b = self._enroll('Bola', 'Balogun', 'ADM-B', self.arm)
        self.student_c = self._enroll('Chidi', 'Chukwu', 'ADM-C', self.other_arm)

        self.summary_a = self._summary(
            self.student_a, AVERAGE_A, 17, REMARK_A, REMARK_ADMIN_A,
        )
        self.summary_b = self._summary(
            self.student_b, Decimal('70.00'), 18, 'HIDDEN-REMARK-B', '',
        )
        self.summary_c = self._summary(
            self.student_c, Decimal('60.00'), 1, 'HIDDEN-REMARK-C', '',
        )
        self.result_a = TermResult.objects.create(
            student=self.student_a,
            subject=self.subject,
            term=self.term,
            computed_score=SCORE_A,
        )
        TermResult.objects.create(
            student=self.student_b,
            subject=self.subject,
            term=self.term,
            computed_score=Decimal('70.10'),
        )

        guardian = Guardian.objects.create(
            user=self.parent,
            full_name='Parent One',
            phone_number='08031111111',
        )
        StudentGuardianLink.objects.create(
            student=self.student_a,
            guardian=guardian,
            is_primary_contact=True,
        )
        guardian_two = Guardian.objects.create(
            user=self.parent_two,
            full_name='Parent Two',
            phone_number='08032222222',
        )
        StudentGuardianLink.objects.create(
            student=self.student_a,
            guardian=guardian_two,
        )
        # Contact on file, but no parent account — must not be notified.
        unclaimed = Guardian.objects.create(
            full_name='Uncle B',
            phone_number='08033333333',
        )
        StudentGuardianLink.objects.create(
            student=self.student_b,
            guardian=unclaimed,
        )
        guardian_c = Guardian.objects.create(
            user=self.parent_other,
            full_name='Parent C',
            phone_number='08034444444',
        )
        StudentGuardianLink.objects.create(
            student=self.student_c,
            guardian=guardian_c,
            is_primary_contact=True,
        )

        self.api = APIClient()
        set_tenant_slug(self.api, self.tenant)

    def _make_user(self, prefix, role, totp=False):
        user = User.objects.create_user(
            email=f'{prefix}@example.com',
            password='pass12345',
            first_name=prefix,
        )
        SchoolMembership.objects.create(user=user, role=role, is_active=True)
        if totp:
            TOTPDevice.objects.create(user=user, name='test', confirmed=True)
        return user

    def _enroll(self, first_name, last_name, admission_number, arm):
        student = Student.objects.create(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date(2014, 1, 1),
            gender=Student.Gender.FEMALE,
            admission_number=admission_number,
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=student,
            class_level=arm.class_level,
            arm=arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )
        return student

    def _summary(self, student, average, position, teacher_remark, admin_remark):
        return TermResultSummary.objects.create(
            student=student,
            term=self.term,
            overall_average=average,
            class_position=position,
            teacher_remark=teacher_remark,
            admin_remark=admin_remark,
        )

    def _results(self, user, student):
        self.api.force_authenticate(user=user)
        return self.api.get(
            RESULTS_URL,
            {'student': str(student.pk), 'term': str(self.term.pk)},
        )

    def _report(self, user, student):
        self.api.force_authenticate(user=user)
        return self.api.get(
            REPORT_URL,
            {'student': str(student.pk), 'term': str(self.term.pk)},
        )

    def _publish(self, user, **overrides):
        self.api.force_authenticate(user=user)
        payload = {
            'class_level': str(self.class_level.pk),
            'arm': str(self.arm.pk),
            'term': str(self.term.pk),
        }
        payload.update(overrides)
        return self.api.post(PUBLISH_URL, payload, format='json')

    def _publish_committed(self, user, **overrides):
        """Run the view and the on-commit notification callback."""
        with mock.patch('communications.tasks.send_notification.delay'), \
                mock.patch('communications.tasks.send_notification.apply_async'):
            with self.captureOnCommitCallbacks(execute=True):
                return self._publish(user, **overrides)

    def _result_logs(self):
        return NotificationLog.objects.filter(
            trigger_type=NotificationLog.TriggerType.RESULT_PUBLISHED,
        )

    def test_parent_cannot_see_unpublished_scores(self):
        response = self._results(self.parent, self.student_a)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data['is_published'])
        self.assertIsNone(response.data['summary'])
        self.assertEqual(response.data['subject_results'], [])
        self.assertEqual(response.data['detail'], RESULTS_NOT_PUBLISHED_DETAIL)
        body = response.content.decode()
        self.assertNotIn('91.25', body)
        self.assertNotIn('88.50', body)
        self.assertNotIn(REMARK_A, body)
        self.assertNotIn(REMARK_ADMIN_A, body)

    def test_parent_cannot_see_subject_scores_when_summary_is_missing(self):
        self.summary_a.delete()
        response = self._results(self.parent, self.student_a)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subject_results'], [])
        self.assertNotIn('91.25', response.content.decode())

    def test_unlinked_parent_is_still_denied(self):
        response = self._results(self.unlinked, self.student_a)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('91.25', response.content.decode())

    def test_parent_cannot_read_another_arms_child(self):
        response = self._results(self.parent, self.student_c)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_and_teacher_see_unpublished_results(self):
        for user in (self.admin, self.teacher):
            response = self._results(user, self.student_a)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertEqual(response.data['summary']['overall_average'], '88.50')
            self.assertEqual(response.data['summary']['class_position'], 17)
            self.assertFalse(response.data['summary']['is_published'])
            self.assertIsNone(response.data['summary']['published_at'])
            self.assertEqual(response.data['summary']['teacher_remark'], REMARK_A)
            self.assertEqual(
                response.data['subject_results'][0]['computed_score'],
                '91.25',
            )

    def test_teacher_still_sees_subject_scores_without_a_summary(self):
        self.summary_a.delete()
        response = self._results(self.teacher, self.student_a)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(response.data['summary'])
        self.assertEqual(
            response.data['subject_results'][0]['computed_score'],
            '91.25',
        )

    def test_parent_report_card_is_blocked_until_publish(self):
        with mock.patch(
            'assessment.views.render_report_card_pdf',
            return_value=b'%PDF',
        ) as render:
            blocked = self._report(self.parent, self.student_a)
        self.assertEqual(blocked.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(blocked.data['detail'], RESULTS_NOT_PUBLISHED_DETAIL)
        render.assert_not_called()

        with mock.patch(
            'assessment.views.render_report_card_pdf',
            return_value=b'%PDF',
        ) as render:
            staff = self._report(self.teacher, self.student_a)
        self.assertEqual(staff.status_code, status.HTTP_200_OK)
        self.assertEqual(staff['Content-Type'], 'application/pdf')
        render.assert_called_once()

    def test_report_card_context_still_builds_before_publish(self):
        context = build_report_card_context(
            student=self.student_a,
            term=self.term,
        )
        self.assertEqual(context['overall_average'], AVERAGE_A)
        self.assertEqual(context['class_position'], 17)
        self.assertEqual(context['teacher_remark'], REMARK_A)
        self.assertEqual(context['subjects'][0]['computed_score'], SCORE_A)

    def test_parent_cannot_list_scores_or_broadsheet(self):
        self.api.force_authenticate(user=self.parent)
        scores = self.api.get(SCORES_URL)
        self.assertEqual(scores.status_code, status.HTTP_403_FORBIDDEN)
        sheet = self.api.get(
            BROADSHEET_URL,
            {
                'class_level': str(self.class_level.pk),
                'arm': str(self.arm.pk),
                'term': str(self.term.pk),
            },
        )
        self.assertEqual(sheet.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_admin_with_2fa_can_publish(self):
        for user in (self.teacher, self.parent, self.bursar, self.admin_no_2fa):
            response = self._publish(user)
            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
                user.email,
            )
        self.summary_a.refresh_from_db()
        self.assertFalse(self.summary_a.is_published)

    def test_publish_rejects_bad_scope(self):
        mismatch = self._publish(
            self.admin,
            arm=str(self.foreign_arm.pk),
        )
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)

        empty = self._publish(
            self.admin,
            class_level=str(self.other_level.pk),
            arm=str(self.foreign_arm.pk),
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No active enrollments', str(empty.data))

    def test_publish_requires_a_summary(self):
        self.summary_c.delete()
        self.api.force_authenticate(user=self.admin)
        response = self.api.post(
            PUBLISH_URL,
            {
                'class_level': str(self.class_level.pk),
                'arm': str(self.other_arm.pk),
                'term': str(self.term.pk),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('recompute', str(response.data).lower())

    def test_publish_releases_the_class_and_leaves_other_arms(self):
        response = self._publish_committed(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['detail'], 'Results published.')
        self.assertEqual(response.data['published_count'], 2)
        self.assertEqual(response.data['newly_published_count'], 2)
        self.assertEqual(response.data['students_without_summary'], 0)
        self.assertTrue(all(row['is_published'] for row in response.data['summaries']))

        self.summary_a.refresh_from_db()
        self.summary_b.refresh_from_db()
        self.summary_c.refresh_from_db()
        self.assertTrue(self.summary_a.is_published)
        self.assertIsNotNone(self.summary_a.published_at)
        self.assertTrue(self.summary_b.is_published)
        self.assertFalse(self.summary_c.is_published)
        self.assertIsNone(self.summary_c.published_at)

        parent = self._results(self.parent, self.student_a)
        self.assertEqual(parent.data['summary']['overall_average'], '88.50')
        self.assertEqual(parent.data['summary']['class_position'], 17)
        self.assertTrue(parent.data['summary']['is_published'])
        self.assertEqual(parent.data['summary']['teacher_remark'], REMARK_A)
        self.assertEqual(parent.data['subject_results'][0]['computed_score'], '91.25')

        other = self._results(self.parent_other, self.student_c)
        self.assertIsNone(other.data['summary'])
        self.assertEqual(other.data['subject_results'], [])

        with mock.patch(
            'assessment.views.render_report_card_pdf',
            return_value=b'%PDF',
        ) as render:
            report = self._report(self.parent, self.student_a)
        self.assertEqual(report.status_code, status.HTTP_200_OK)
        render.assert_called_once()

    def test_publish_counts_students_who_still_need_recompute(self):
        extra = self._enroll('Dupe', 'Dada', 'ADM-D', self.arm)
        response = self._publish_committed(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['published_count'], 2)
        self.assertEqual(response.data['students_without_summary'], 1)
        self.assertFalse(
            TermResultSummary.objects.filter(student=extra, term=self.term).exists()
        )

    def test_notifications_wait_for_commit_and_cover_both_channels(self):
        calls = []

        def record(summary, recipient):
            calls.append((summary.pk, recipient.pk))

        with mock.patch(
            'communications.email_service.EmailNotificationService.send_result_published',
            side_effect=record,
        ), mock.patch(
            'communications.whatsapp_service.WhatsAppNotificationService.send_result_published',
            side_effect=record,
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self._publish(self.admin)
                self.assertEqual(calls, [])
                self.summary_a.refresh_from_db()
                self.assertTrue(self.summary_a.is_published)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()

        self.assertEqual(len(calls), 4)
        self.assertEqual(
            {recipient for _summary, recipient in calls},
            {self.parent.pk, self.parent_two.pk},
        )
        self.assertTrue(all(summary_id == self.summary_a.pk for summary_id, _ in calls))

    def test_publish_queues_email_and_whatsapp_once(self):
        first = self._publish_committed(self.admin)
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        logs = list(self._result_logs())
        self.assertEqual(len(logs), 4)
        self.assertEqual(
            {log.channel for log in logs},
            {NotificationLog.Channel.EMAIL, NotificationLog.Channel.WHATSAPP},
        )
        self.assertEqual(
            {log.recipient_id for log in logs},
            {self.parent.pk, self.parent_two.pk},
        )
        self.assertTrue(all(log.related_object_id == self.summary_a.pk for log in logs))
        self.assertTrue(
            all(log.status == NotificationLog.Status.QUEUED for log in logs)
        )

        self.summary_a.refresh_from_db()
        first_published_at = self.summary_a.published_at
        self.assertIsNotNone(first_published_at)
        second = self._publish_committed(self.admin)
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(second.data['newly_published_count'], 0)
        self.assertEqual(second.data['detail'], 'Results were already published.')
        self.assertEqual(self._result_logs().count(), 4)
        self.summary_a.refresh_from_db()
        self.assertGreaterEqual(self.summary_a.published_at, first_published_at)

    def test_notification_failure_does_not_unpublish(self):
        with mock.patch(
            'communications.email_service.EmailNotificationService.send_result_published',
            side_effect=RuntimeError('broker down'),
        ), mock.patch(
            'communications.whatsapp_service.WhatsAppNotificationService.send_result_published',
            side_effect=RuntimeError('broker down'),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self._publish(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.summary_a.refresh_from_db()
        self.assertTrue(self.summary_a.is_published)
        self.assertEqual(self._result_logs().count(), 0)

    def test_recompute_preserves_publication_and_does_not_notify(self):
        published_at = timezone.now()
        self.summary_a.is_published = True
        self.summary_a.published_at = published_at
        self.summary_a.teacher_remark = 'Keep me'
        self.summary_a.save(
            update_fields=['is_published', 'published_at', 'teacher_remark'],
        )

        recompute_class_term_summaries(
            class_level=self.class_level,
            arm=self.arm,
            term=self.term,
        )
        self.summary_a.refresh_from_db()
        self.summary_b.refresh_from_db()
        self.assertTrue(self.summary_a.is_published)
        self.assertEqual(self.summary_a.published_at, published_at)
        self.assertEqual(self.summary_a.teacher_remark, 'Keep me')
        self.assertFalse(self.summary_b.is_published)
        self.assertIsNone(self.summary_b.published_at)
        self.assertEqual(NotificationLog.objects.count(), 0)

        self.api.force_authenticate(user=self.admin)
        response = self.api.post(
            RECOMPUTE_URL,
            {
                'class_level': str(self.class_level.pk),
                'arm': str(self.other_arm.pk),
                'term': str(self.term.pk),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = response.data['summaries'][0]
        self.assertFalse(row['is_published'])
        self.assertIsNone(row['published_at'])
        self.summary_c.refresh_from_db()
        self.assertFalse(self.summary_c.is_published)
