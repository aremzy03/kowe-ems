import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

WEIGHT_TOTAL_REQUIRED = Decimal('100')


def scheme_weight_sum(
    *,
    subject_id,
    class_level_id,
    term_id,
    exclude_pk=None,
):
    """Sum of ``weight_percentage`` for a subject + class_level + term scheme."""
    qs = AssessmentComponent.objects.filter(
        subject_id=subject_id,
        class_level_id=class_level_id,
        term_id=term_id,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    total = qs.aggregate(total=Sum('weight_percentage'))['total']
    return total if total is not None else Decimal('0')


def validate_scheme_weights_equal_100(
    *,
    subject_id,
    class_level_id,
    term_id,
    exclude_pk=None,
    proposed_weight=None,
    allow_empty=False,
):
    """
    Ensure weights for this scheme sum to exactly 100.

    If ``proposed_weight`` is set, it replaces ``exclude_pk``'s contribution
    (create: exclude_pk=None; update: exclude_pk=instance.pk).

    ``allow_empty``: treat zero components as valid (used after deleting the
    last component of a scheme).
    """
    others = scheme_weight_sum(
        subject_id=subject_id,
        class_level_id=class_level_id,
        term_id=term_id,
        exclude_pk=exclude_pk,
    )
    if proposed_weight is not None:
        total = others + Decimal(str(proposed_weight))
    else:
        total = others

    if allow_empty and total == Decimal('0') and proposed_weight is None:
        return total

    if total != WEIGHT_TOTAL_REQUIRED:
        raise ValidationError(
            f'Assessment component weights for this subject, class level, and '
            f'term must sum to {WEIGHT_TOTAL_REQUIRED}%. '
            f'Current total would be {total}%.'
        )
    return total


class AssessmentComponent(models.Model):
    """
    Weighted continuous-assessment piece for a subject/class/term scheme.

    Tenant-scoped. All components sharing the same subject + class_level + term
    must have weight_percentage values that sum to exactly 100.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.PROTECT,
        related_name='assessment_components',
    )
    class_level = models.ForeignKey(
        'academics.ClassLevel',
        on_delete=models.PROTECT,
        related_name='assessment_components',
    )
    term = models.ForeignKey(
        'academics.Term',
        on_delete=models.PROTECT,
        related_name='assessment_components',
    )
    name = models.CharField(max_length=100)
    weight_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Share of the subject term total (all components must sum to 100).',
    )
    max_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Maximum raw marks for this component (e.g. 100).',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['term', 'class_level', 'subject', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'class_level', 'term', 'name'],
                name='uniq_assessment_component_scheme_name',
            ),
        ]

    def __str__(self):
        return (
            f'{self.name} ({self.weight_percentage}%) — '
            f'{self.subject} / {self.class_level} / {self.term}'
        )

    def clean(self):
        super().clean()
        if (
            self.subject_id is None
            or self.class_level_id is None
            or self.term_id is None
            or self.weight_percentage is None
        ):
            return
        try:
            validate_scheme_weights_equal_100(
                subject_id=self.subject_id,
                class_level_id=self.class_level_id,
                term_id=self.term_id,
                exclude_pk=self.pk if self.pk else None,
                proposed_weight=self.weight_percentage,
            )
        except ValidationError as exc:
            raise ValidationError({'weight_percentage': exc.messages}) from exc


class Score(models.Model):
    """
    Raw mark for one student on one assessment component.

    Unique on (student, assessment_component) so bulk / offline retries upsert
    instead of duplicating rows.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='scores',
    )
    assessment_component = models.ForeignKey(
        AssessmentComponent,
        on_delete=models.PROTECT,
        related_name='scores',
    )
    score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='scores_entered',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['assessment_component', 'student']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'assessment_component'],
                name='uniq_score_student_component',
            ),
        ]

    def __str__(self):
        return (
            f'{self.student} / {self.assessment_component.name}: {self.score}'
        )

    def clean(self):
        super().clean()
        if self.assessment_component_id is None or self.score is None:
            return
        max_score = self.assessment_component.max_score
        if self.score > max_score:
            raise ValidationError(
                {
                    'score': (
                        f'Score {self.score} exceeds max score '
                        f'{max_score} for {self.assessment_component.name}.'
                    )
                }
            )
        if self.score < Decimal('0'):
            raise ValidationError({'score': 'Score cannot be negative.'})


class AuditLog(models.Model):
    """
    Automatic grade-change trail for Score create/update.

    Kept in ``assessment`` (not a shared core app): fields are score-specific
    (Decimal old/new + assessment_component FK). Attendance uses a parallel
    ``attendance.AttendanceAuditLog`` with the same signal/no-op pattern —
    schemas differ enough that a shared polymorphic table would dilute type
    safety without helping Phase 2's existing audit API.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='score_audit_logs',
    )
    assessment_component = models.ForeignKey(
        AssessmentComponent,
        on_delete=models.PROTECT,
        related_name='score_audit_logs',
    )
    old_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Previous score; null on first create.',
    )
    new_value = models.DecimalField(max_digits=8, decimal_places=2)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='score_audit_logs',
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return (
            f'{self.student} / {self.assessment_component_id}: '
            f'{self.old_value} → {self.new_value} @ {self.timestamp}'
        )


class TermResult(models.Model):
    """
    Materialized weighted subject total for one student in one term.

    Recomputed explicitly (service / recompute endpoint / management command),
    never via Score save signals — mid-entry rank flicker is avoided by design.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='term_results',
    )
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.PROTECT,
        related_name='term_results',
    )
    term = models.ForeignKey(
        'academics.Term',
        on_delete=models.PROTECT,
        related_name='term_results',
    )
    computed_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=(
            'Weighted sum across components: '
            'Σ (raw/max_score × weight_percentage). Out of 100 when the '
            'scheme is complete and all components are scored.'
        ),
    )
    computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['term', 'student', 'subject']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'subject', 'term'],
                name='uniq_term_result_student_subject_term',
            ),
        ]

    def __str__(self):
        return (
            f'{self.student} / {self.subject} / {self.term}: '
            f'{self.computed_score}'
        )


class TermResultSummary(models.Model):
    """
    Materialized overall average + class position for one student in one term.

    ``class_position`` is ranked within the student's active enrollment
    class_level + arm + term.     Recomputed in batch for the whole class so
    ranks stay consistent; never updated on individual Score saves.

    ``is_published`` is the parent release gate. Recompute creates rows
    unpublished and does not clear the flag. Parents see the summary,
    subject totals, and report-card PDF only after an admin publishes
    the class. Admin and teacher reads ignore the flag.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='term_result_summaries',
    )
    term = models.ForeignKey(
        'academics.Term',
        on_delete=models.PROTECT,
        related_name='term_result_summaries',
    )
    overall_average = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text='Mean of this student\'s TermResult.computed_score values.',
    )
    class_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            'Competition rank (1,2,2,4) within class_level+arm+term; '
            'null until a class recompute has run.'
        ),
    )
    teacher_remark = models.TextField(blank=True, default='')
    admin_remark = models.TextField(blank=True, default='')
    computed_at = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(
        default=False,
        help_text=(
            'Parents and the report-card download see this summary only '
            'after an admin publishes the class. Teachers and admins '
            'always see it.'
        ),
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set when an admin publishes this summary. Null until then.',
    )

    class Meta:
        ordering = ['term', 'class_position', 'student']
        verbose_name_plural = 'term result summaries'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'term'],
                name='uniq_term_result_summary_student_term',
            ),
        ]

    def __str__(self):
        pos = self.class_position if self.class_position is not None else '—'
        return (
            f'{self.student} / {self.term}: avg={self.overall_average} '
            f'pos={pos}'
        )
