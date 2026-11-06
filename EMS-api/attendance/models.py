import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class DailyAttendance(models.Model):
    """
    One attendance mark per student per calendar day.

    Unique on (student, date) so bulk / offline retries upsert instead of
    duplicating rows — independent of how many subjects the student has.
    Marking authority is the form/class teacher (ClassTeacherAssignment),
    not ClassSubjectAssignment.
    """

    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'
        EXCUSED = 'excused', 'Excused'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='daily_attendance',
    )
    class_level = models.ForeignKey(
        'academics.ClassLevel',
        on_delete=models.PROTECT,
        related_name='daily_attendance',
    )
    arm = models.ForeignKey(
        'academics.Arm',
        on_delete=models.PROTECT,
        related_name='daily_attendance',
    )
    term = models.ForeignKey(
        'academics.Term',
        on_delete=models.PROTECT,
        related_name='daily_attendance',
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='attendance_marked',
    )
    remarks = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'student']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'date'],
                name='uniq_daily_attendance_student_date',
            ),
        ]

    def __str__(self):
        return f'{self.student} @ {self.date}: {self.status}'


class AttendanceAuditLog(models.Model):
    """
    Automatic trail for DailyAttendance create / status changes.

    Domain-specific (not a shared core AuditLog): score audits use Decimal
    + assessment_component; attendance audits use status CharFields + date.
    Same signal pattern as assessment.AuditLog — no-op retries do not write.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='attendance_audit_logs',
    )
    date = models.DateField(db_index=True)
    old_status = models.CharField(
        max_length=20,
        choices=DailyAttendance.Status.choices,
        null=True,
        blank=True,
        help_text='Previous status; null on first create.',
    )
    new_status = models.CharField(
        max_length=20,
        choices=DailyAttendance.Status.choices,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='attendance_audit_logs',
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return (
            f'{self.student} @ {self.date}: '
            f'{self.old_status} → {self.new_status} @ {self.timestamp}'
        )
