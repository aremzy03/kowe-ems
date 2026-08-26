"""
Signal-based Score audit logging.

Teachers / endpoints must not call AuditLog manually — every real score
create or value change writes one row; identical re-saves are skipped.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from assessment.models import AuditLog, Score


@receiver(pre_save, sender=Score)
def score_cache_previous_value(sender, instance, **kwargs):
    """Stash the prior score so post_save can detect real changes."""
    if instance.pk is None:
        instance._audit_old_value = None
        return
    try:
        previous = Score.objects.only('score').get(pk=instance.pk)
        instance._audit_old_value = previous.score
    except Score.DoesNotExist:
        instance._audit_old_value = None


@receiver(post_save, sender=Score)
def score_write_audit_log(sender, instance, created, **kwargs):
    """
    Write AuditLog on create or when ``score`` actually changes.

    No-op updates (same numeric value, e.g. idempotent bulk retry) do not
    create an audit row.
    """
    old_value = getattr(instance, '_audit_old_value', None)
    new_value = instance.score

    if not created and old_value == new_value:
        return

    AuditLog.objects.create(
        student_id=instance.student_id,
        assessment_component_id=instance.assessment_component_id,
        old_value=old_value,
        new_value=new_value,
        changed_by_id=instance.entered_by_id,
    )
