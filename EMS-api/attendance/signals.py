"""
Signal-based DailyAttendance audit logging.

Endpoints must not call AttendanceAuditLog manually — every real create or
status change writes one row; identical re-saves (idempotent bulk retry) skip.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from attendance.models import AttendanceAuditLog, DailyAttendance


@receiver(pre_save, sender=DailyAttendance)
def attendance_cache_previous_status(sender, instance, **kwargs):
    """Stash the prior status so post_save can detect real changes."""
    if instance.pk is None:
        instance._audit_old_status = None
        return
    try:
        previous = DailyAttendance.objects.only('status').get(pk=instance.pk)
        instance._audit_old_status = previous.status
    except DailyAttendance.DoesNotExist:
        instance._audit_old_status = None


@receiver(post_save, sender=DailyAttendance)
def attendance_write_audit_log(sender, instance, created, **kwargs):
    """
    Write AttendanceAuditLog on create or when ``status`` actually changes.

    No-op updates (same status, e.g. idempotent bulk retry) and remarks-only
    edits do not create an audit row.
    """
    old_status = getattr(instance, '_audit_old_status', None)
    new_status = instance.status

    if not created and old_status == new_status:
        return

    AttendanceAuditLog.objects.create(
        student_id=instance.student_id,
        date=instance.date,
        old_status=old_status,
        new_status=new_status,
        changed_by_id=instance.marked_by_id,
    )
