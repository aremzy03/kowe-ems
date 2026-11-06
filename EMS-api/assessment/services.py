"""
Scheme helpers for AssessmentComponent (set / clone) and Score upsert.

Schemes are keyed by (subject, class_level, term). Weights across the scheme
must always sum to exactly 100 after a successful write.

Score upsert is idempotent on (student, assessment_component): retries update
in place and never duplicate rows (Phase 2 Prompt 3 / Prompt 7 offline check).

Term averages and class ranks are materialized in TermResult / TermResultSummary
and recomputed only via explicit service calls (API recompute endpoint or
management command) — never on Score save — so ranks do not flicker mid-entry.

Broadsheet (Prompt 5) is a read-only grid: live weighted subject totals from
current Scores for table display; ranks still require explicit recompute.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from academics.models import Enrollment
from academics.teacher_assignments import teacher_has_assignment
from assessment.models import (
    WEIGHT_TOTAL_REQUIRED,
    AssessmentComponent,
    Score,
    TermResult,
    TermResultSummary,
    validate_scheme_weights_equal_100,
)
from memberships.models import SchoolMembership
from memberships.permissions import resolve_request_membership

logger = logging.getLogger(__name__)

TWOPLACES = Decimal('0.01')


def _quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _weights_sum(components):
    return sum((Decimal(str(c['weight_percentage'])) for c in components), Decimal('0'))


@transaction.atomic
def replace_scheme(*, subject, class_level, term, components):
    """
    Replace all components for subject+class_level+term with ``components``.

    ``components`` is a list of dicts with keys:
    name, weight_percentage, max_score.

    Raises ``django.core.exceptions.ValidationError`` if weights ≠ 100 or
    names collide within the payload.
    """
    if not components:
        AssessmentComponent.objects.filter(
            subject=subject,
            class_level=class_level,
            term=term,
        ).delete()
        return []

    total = _weights_sum(components)
    if total != WEIGHT_TOTAL_REQUIRED:
        from django.core.exceptions import ValidationError

        raise ValidationError(
            f'Assessment component weights for this subject, class level, and '
            f'term must sum to {WEIGHT_TOTAL_REQUIRED}%. '
            f'Current total would be {total}%.'
        )

    names = [c['name'].strip() for c in components]
    if len(names) != len(set(names)):
        from django.core.exceptions import ValidationError

        raise ValidationError(
            'Component names must be unique within a subject/class/term scheme.'
        )

    AssessmentComponent.objects.filter(
        subject=subject,
        class_level=class_level,
        term=term,
    ).delete()

    created = [
        AssessmentComponent.objects.create(
            subject=subject,
            class_level=class_level,
            term=term,
            name=item['name'].strip(),
            weight_percentage=item['weight_percentage'],
            max_score=item['max_score'],
        )
        for item in components
    ]
    # Defense in depth after write.
    validate_scheme_weights_equal_100(
        subject_id=subject.pk,
        class_level_id=class_level.pk,
        term_id=term.pk,
    )
    return created


@transaction.atomic
def clone_scheme(
    *,
    source_subject,
    source_class_level,
    source_term,
    target_subject,
    target_class_level,
    target_term,
    overwrite=False,
):
    """
    Copy components from a source scheme onto a target subject/class/term.

    If the target already has components and ``overwrite`` is False, raises
    ValidationError. When ``overwrite`` is True, target components are replaced.
    """
    from django.core.exceptions import ValidationError

    source_qs = AssessmentComponent.objects.filter(
        subject=source_subject,
        class_level=source_class_level,
        term=source_term,
    ).order_by('name')
    if not source_qs.exists():
        raise ValidationError(
            'Source scheme has no assessment components to clone.'
        )

    # Source must already be a valid 100% scheme.
    validate_scheme_weights_equal_100(
        subject_id=source_subject.pk,
        class_level_id=source_class_level.pk,
        term_id=source_term.pk,
    )

    target_exists = AssessmentComponent.objects.filter(
        subject=target_subject,
        class_level=target_class_level,
        term=target_term,
    ).exists()
    if target_exists and not overwrite:
        raise ValidationError(
            'Target scheme already has components. Pass overwrite=true to replace them.'
        )

    payload = [
        {
            'name': c.name,
            'weight_percentage': c.weight_percentage,
            'max_score': c.max_score,
        }
        for c in source_qs
    ]
    return replace_scheme(
        subject=target_subject,
        class_level=target_class_level,
        term=target_term,
        components=payload,
    )


def enrollment_for_score_scope(*, student, assessment_component):
    """
    Active enrollment placing ``student`` in the component's class_level+term.

    Arm comes from enrollment — required for ClassSubjectAssignment checks
    (components have no arm; teachers are assigned per arm).
    """
    return (
        Enrollment.objects.filter(
            student_id=student.pk if hasattr(student, 'pk') else student,
            class_level_id=assessment_component.class_level_id,
            term_id=assessment_component.term_id,
            status=Enrollment.Status.ACTIVE,
        )
        .select_related('arm', 'class_level', 'term')
        .first()
    )


def assignment_scope_for_score(*, student, assessment_component):
    """
    Return (subject_id, class_level_id, arm_id, term_id) for a score target.

    ``arm_id`` is None when the student has no matching active enrollment.
    """
    enrollment = enrollment_for_score_scope(
        student=student,
        assessment_component=assessment_component,
    )
    return (
        assessment_component.subject_id,
        assessment_component.class_level_id,
        enrollment.arm_id if enrollment is not None else None,
        assessment_component.term_id,
    )


def validate_score_value(*, score, assessment_component):
    """Reject scores outside [0, max_score] with a clear message (no clamping)."""
    score = Decimal(str(score))
    max_score = assessment_component.max_score
    if score < Decimal('0'):
        raise ValidationError({'score': 'Score cannot be negative.'})
    if score > max_score:
        raise ValidationError(
            {
                'score': (
                    f'Score {score} exceeds max score {max_score} for '
                    f'{assessment_component.name}.'
                )
            }
        )
    return score


def assert_actor_may_enter_score(*, request, student, assessment_component):
    """
    Admin: any score in the tenant (student must still be enrolled).
    Teacher: must hold ClassSubjectAssignment for the student's arm +
    component subject/class/term.
    """
    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    enrollment = enrollment_for_score_scope(
        student=student,
        assessment_component=assessment_component,
    )
    if enrollment is None:
        raise ValidationError(
            {
                'student_id': (
                    'Student has no active enrollment for this component\'s '
                    'class level and term.'
                )
            }
        )

    if membership.role == SchoolMembership.Role.ADMIN:
        return enrollment

    if membership.role != SchoolMembership.Role.TEACHER:
        raise ValidationError(
            'Only school admins or assigned teachers may enter scores.'
        )

    if not teacher_has_assignment(
        request.user,
        subject_id=assessment_component.subject_id,
        class_level_id=assessment_component.class_level_id,
        arm_id=enrollment.arm_id,
        term_id=assessment_component.term_id,
    ):
        raise ValidationError(
            'You are not assigned to teach this class/subject/term. '
            'Ask a school admin to create a ClassSubjectAssignment.'
        )
    return enrollment



@transaction.atomic
def upsert_score(*, student, assessment_component, score, entered_by):
    """
    Create or update a Score for (student, assessment_component).

    Idempotent: submitting the same score again returns the existing row
    without rewriting (so AuditLog signals do not fire a no-op change).

    Returns ``(score_obj, created, changed)``.
    """
    score = validate_score_value(
        score=score,
        assessment_component=assessment_component,
    )

    existing = (
        Score.objects.select_for_update()
        .filter(
            student_id=student.pk,
            assessment_component_id=assessment_component.pk,
        )
        .first()
    )
    if existing is not None:
        if existing.score == score:
            return existing, False, False
        existing.score = score
        existing.entered_by = entered_by
        existing.full_clean()
        existing.save()
        return existing, False, True

    try:
        # Savepoint so a concurrent-create IntegrityError does not abort
        # the outer atomic block (PostgreSQL).
        with transaction.atomic():
            obj = Score(
                student=student,
                assessment_component=assessment_component,
                score=score,
                entered_by=entered_by,
            )
            obj.full_clean()
            obj.save()
            return obj, True, True
    except IntegrityError:
        existing = Score.objects.select_for_update().get(
            student_id=student.pk,
            assessment_component_id=assessment_component.pk,
        )
        if existing.score == score:
            return existing, False, False
        existing.score = score
        existing.entered_by = entered_by
        existing.full_clean()
        existing.save()
        return existing, False, True


def compute_weighted_subject_score(*, student_id, subject_id, term_id, class_level_id):
    """
    Weighted subject total from Scores × AssessmentComponent weights.

    Formula per component: (raw_score / max_score) × weight_percentage.
    Missing scores contribute 0 (partial entry still produces a total).
    Returns Decimal quantized to 2 places. If the scheme has no components,
    returns Decimal('0').
    """
    components = list(
        AssessmentComponent.objects.filter(
            subject_id=subject_id,
            class_level_id=class_level_id,
            term_id=term_id,
        )
    )
    if not components:
        return Decimal('0.00')

    scores_by_component = {
        row.assessment_component_id: row.score
        for row in Score.objects.filter(
            student_id=student_id,
            assessment_component_id__in=[c.pk for c in components],
        )
    }

    total = Decimal('0')
    for component in components:
        raw = scores_by_component.get(component.pk)
        if raw is None:
            continue
        if component.max_score <= 0:
            continue
        contribution = (
            Decimal(str(raw)) / Decimal(str(component.max_score))
        ) * Decimal(str(component.weight_percentage))
        total += contribution
    return _quantize(total)


@transaction.atomic
def recompute_term_result(*, student, subject, term, class_level_id=None):
    """
    Upsert TermResult for one student + subject + term.

    ``class_level_id`` defaults to the student's active enrollment for ``term``.
    Does not touch TermResultSummary / class ranks — call
    ``recompute_class_term_summaries`` after score entry is finished.
    """
    student_id = student.pk if hasattr(student, 'pk') else student
    subject_id = subject.pk if hasattr(subject, 'pk') else subject
    term_id = term.pk if hasattr(term, 'pk') else term

    if class_level_id is None:
        enrollment = (
            Enrollment.objects.filter(
                student_id=student_id,
                term_id=term_id,
                status=Enrollment.Status.ACTIVE,
            )
            .only('class_level_id')
            .first()
        )
        if enrollment is None:
            raise ValidationError(
                {
                    'student': (
                        'Student has no active enrollment for this term; '
                        'cannot resolve class level for the assessment scheme.'
                    )
                }
            )
        class_level_id = enrollment.class_level_id

    computed_score = compute_weighted_subject_score(
        student_id=student_id,
        subject_id=subject_id,
        term_id=term_id,
        class_level_id=class_level_id,
    )
    now = timezone.now()
    obj, _created = TermResult.objects.update_or_create(
        student_id=student_id,
        subject_id=subject_id,
        term_id=term_id,
        defaults={
            'computed_score': computed_score,
            'computed_at': now,
        },
    )
    return obj


def _competition_ranks(ordered_averages):
    """
    Competition ranking (1, 2, 2, 4) over a sequence of Decimal averages
    already sorted descending. Equal averages share the same position;
    the next distinct average skips ahead.
    """
    ranks = []
    position = 1
    for index, average in enumerate(ordered_averages):
        if index > 0 and average < ordered_averages[index - 1]:
            position = index + 1
        ranks.append(position)
    return ranks


@transaction.atomic
def recompute_class_term_summaries(*, class_level, arm, term):
    """
    Recompute TermResult for every enrolled student × scheme subject, then
    TermResultSummary overall_average + class_position for the whole class.

    Ranking is competition-style within this class_level + arm + term.
    Remarks on existing TermResultSummary rows are preserved.

    ``is_published`` and ``published_at`` are preserved. Recompute does
    not release results and does not queue parent notifications. New
    summary rows stay unpublished (model default).
    """
    class_level_id = class_level.pk if hasattr(class_level, 'pk') else class_level
    arm_id = arm.pk if hasattr(arm, 'pk') else arm
    term_id = term.pk if hasattr(term, 'pk') else term

    enrollments = list(
        Enrollment.objects.filter(
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            status=Enrollment.Status.ACTIVE,
        )
        .select_related('student')
        .order_by('student__last_name', 'student__first_name', 'student_id')
    )

    subject_ids = list(
        AssessmentComponent.objects.filter(
            class_level_id=class_level_id,
            term_id=term_id,
        )
        .values_list('subject_id', flat=True)
        .distinct()
    )

    now = timezone.now()
    subject_results_written = 0

    for enrollment in enrollments:
        student = enrollment.student
        for subject_id in subject_ids:
            recompute_term_result(
                student=student,
                subject=subject_id,
                term=term_id,
                class_level_id=class_level_id,
            )
            subject_results_written += 1

    # Build averages from freshly written TermResults (only subjects in scheme).
    averages = []
    for enrollment in enrollments:
        student_id = enrollment.student_id
        results = list(
            TermResult.objects.filter(
                student_id=student_id,
                term_id=term_id,
                subject_id__in=subject_ids,
            ).values_list('computed_score', flat=True)
        )
        if results:
            overall = _quantize(
                sum(results, Decimal('0')) / Decimal(len(results))
            )
        else:
            overall = Decimal('0.00')
        averages.append(
            {
                'student_id': student_id,
                'overall_average': overall,
                'last_name': enrollment.student.last_name,
                'first_name': enrollment.student.first_name,
            }
        )

    # Sort: higher average first; tie-break name for stable ordering of equals.
    averages.sort(
        key=lambda row: (
            -row['overall_average'],
            row['last_name'].lower(),
            row['first_name'].lower(),
            str(row['student_id']),
        )
    )
    ranks = _competition_ranks([row['overall_average'] for row in averages])

    summaries = []
    for row, position in zip(averages, ranks, strict=True):
        summary, _created = TermResultSummary.objects.update_or_create(
            student_id=row['student_id'],
            term_id=term_id,
            defaults={
                'overall_average': row['overall_average'],
                'class_position': position,
                'computed_at': now,
                # Publication is an admin action. Omit is_published and
                # published_at so a recompute cannot release or retract.
            },
        )
        summaries.append(summary)

    return {
        'class_level_id': class_level_id,
        'arm_id': arm_id,
        'term_id': term_id,
        'students': len(enrollments),
        'subjects': len(subject_ids),
        'term_results_upserted': subject_results_written,
        'summaries': summaries,
        'computed_at': now,
    }


def assert_actor_may_recompute_class(*, request, class_level, arm, term):
    """
    Admin: any class. Teacher: must hold at least one ClassSubjectAssignment
    for this class_level + arm + term (any subject).
    """
    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    if membership.role == SchoolMembership.Role.ADMIN:
        return

    if membership.role != SchoolMembership.Role.TEACHER:
        raise ValidationError(
            'Only school admins or assigned teachers may recompute results.'
        )

    from academics.models import ClassSubjectAssignment

    has_any = ClassSubjectAssignment.objects.filter(
        teacher_id=request.user.pk,
        class_level_id=class_level.pk if hasattr(class_level, 'pk') else class_level,
        arm_id=arm.pk if hasattr(arm, 'pk') else arm,
        term_id=term.pk if hasattr(term, 'pk') else term,
    ).exists()
    if not has_any:
        raise ValidationError(
            'You are not assigned to teach any subject in this class/arm/term. '
            'Ask a school admin to create a ClassSubjectAssignment.'
        )


def assert_actor_may_view_broadsheet(
    *,
    request,
    class_level,
    arm,
    term,
    subject=None,
):
    """
    Admin: any class broadsheet (optional subject filter).
    Teacher: only class_level+arm+term they are assigned to; subjects limited
    to their ClassSubjectAssignment rows (optional subject must be one of them).

    Returns ``(membership, allowed_subject_ids)`` where ``allowed_subject_ids``
    is ``None`` for admin (all subjects) or a list of UUIDs for teachers.
    """
    from academics.models import ClassSubjectAssignment

    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    class_level_id = class_level.pk if hasattr(class_level, 'pk') else class_level
    arm_id = arm.pk if hasattr(arm, 'pk') else arm
    term_id = term.pk if hasattr(term, 'pk') else term
    subject_id = (
        None
        if subject is None
        else (subject.pk if hasattr(subject, 'pk') else subject)
    )

    if membership.role == SchoolMembership.Role.ADMIN:
        return membership, None

    if membership.role != SchoolMembership.Role.TEACHER:
        raise ValidationError(
            'Only school admins or assigned teachers may view the broadsheet.'
        )

    assigned_subject_ids = list(
        ClassSubjectAssignment.objects.filter(
            teacher_id=request.user.pk,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
        )
        .values_list('subject_id', flat=True)
        .distinct()
    )
    if not assigned_subject_ids:
        raise ValidationError(
            'You are not assigned to teach any subject in this class/arm/term. '
            'Ask a school admin to create a ClassSubjectAssignment.'
        )

    if subject_id is not None and subject_id not in assigned_subject_ids:
        raise ValidationError(
            'You are not assigned to teach this subject in this class/arm/term.'
        )

    return membership, assigned_subject_ids


def build_broadsheet(*, class_level, arm, term, subject_ids=None, subject=None):
    """
    Build a table-ready broadsheet payload for one class_level + arm + term.

    ``subject_ids``: when set (teacher scope), only those subjects appear.
    ``subject``: optional further narrow to one subject (admin or teacher).

    Subject totals are **live** weighted sums from current Scores (same formula
    as TermResult recompute) so the grid stays useful during mark entry
    without requiring an explicit recompute. Rankings / TermResultSummary are
    unchanged until ``recompute_class_term_summaries``.

    Returns a dict shaped for a frontend table:
    - ``columns``: component columns + one ``subject_total`` column per subject
    - ``rows``: one per enrolled student; ``cells[column.key]`` holds the value
    """
    class_level_id = class_level.pk if hasattr(class_level, 'pk') else class_level
    arm_id = arm.pk if hasattr(arm, 'pk') else arm
    term_id = term.pk if hasattr(term, 'pk') else term
    subject_filter_id = (
        None
        if subject is None
        else (subject.pk if hasattr(subject, 'pk') else subject)
    )

    components_qs = (
        AssessmentComponent.objects.filter(
            class_level_id=class_level_id,
            term_id=term_id,
        )
        .select_related('subject')
        .order_by('subject__name', 'name')
    )
    if subject_ids is not None:
        components_qs = components_qs.filter(subject_id__in=subject_ids)
    if subject_filter_id is not None:
        components_qs = components_qs.filter(subject_id=subject_filter_id)

    components = list(components_qs)
    # Preserve subject order as first-seen in the ordered component list.
    subjects_ordered = []
    seen_subjects = set()
    components_by_subject = {}
    for component in components:
        sid = component.subject_id
        if sid not in seen_subjects:
            seen_subjects.add(sid)
            subjects_ordered.append(component.subject)
            components_by_subject[sid] = []
        components_by_subject[sid].append(component)

    columns = []
    for subj in subjects_ordered:
        for component in components_by_subject[subj.pk]:
            columns.append(
                {
                    'key': f'comp_{component.pk}',
                    'kind': 'component',
                    'label': component.name,
                    'subject': str(subj.pk),
                    'subject_name': subj.name,
                    'subject_code': subj.code,
                    'assessment_component_id': str(component.pk),
                    'weight_percentage': str(component.weight_percentage),
                    'max_score': str(component.max_score),
                }
            )
        columns.append(
            {
                'key': f'total_{subj.pk}',
                'kind': 'subject_total',
                'label': f'{subj.name} Total',
                'subject': str(subj.pk),
                'subject_name': subj.name,
                'subject_code': subj.code,
                'assessment_component_id': None,
                'weight_percentage': None,
                'max_score': None,
            }
        )

    enrollments = list(
        Enrollment.objects.filter(
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            status=Enrollment.Status.ACTIVE,
        )
        .select_related('student')
        .order_by('student__last_name', 'student__first_name', 'student_id')
    )

    component_ids = [c.pk for c in components]
    student_ids = [e.student_id for e in enrollments]
    scores = Score.objects.filter(
        student_id__in=student_ids,
        assessment_component_id__in=component_ids,
    ).only('student_id', 'assessment_component_id', 'score')
    score_map = {
        (row.student_id, row.assessment_component_id): row.score for row in scores
    }

    def _live_total(student_id, subject_id):
        """Same formula as compute_weighted_subject_score, using score_map."""
        total = Decimal('0')
        for component in components_by_subject.get(subject_id, []):
            raw = score_map.get((student_id, component.pk))
            if raw is None or component.max_score <= 0:
                continue
            total += (
                Decimal(str(raw)) / Decimal(str(component.max_score))
            ) * Decimal(str(component.weight_percentage))
        return _quantize(total)

    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        cells = {}
        for component in components:
            key = f'comp_{component.pk}'
            raw = score_map.get((student.pk, component.pk))
            cells[key] = str(raw) if raw is not None else None
        for subj in subjects_ordered:
            cells[f'total_{subj.pk}'] = str(_live_total(student.pk, subj.pk))
        rows.append(
            {
                'student': str(student.pk),
                'student_name': f'{student.last_name}, {student.first_name}',
                'admission_number': student.admission_number,
                'cells': cells,
            }
        )

    return {
        'class_level': str(class_level_id),
        'class_level_name': class_level.name,
        'arm': str(arm_id),
        'arm_name': arm.name,
        'term': str(term_id),
        'term_name': term.name,
        'subjects': [
            {
                'subject': str(s.pk),
                'subject_name': s.name,
                'subject_code': s.code,
                'component_count': len(components_by_subject[s.pk]),
            }
            for s in subjects_ordered
        ],
        'columns': columns,
        'rows': rows,
        'student_count': len(rows),
        'stale_hint': (
            'Subject totals are live-weighted from current Scores '
            '(raw/max × weight). Class ranks and TermResultSummary still '
            'require POST /api/assessment/results/recompute/ after mark entry.'
        ),
    }


def assert_actor_may_view_student_term_results(*, request, student, term):
    """
    Admin: any student. Teacher: assigned to the student's enrollment class
    for this term (any subject). Parent: linked via StudentGuardianLink.
    """
    from academics.parent_access import parent_has_link_to_student

    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    if membership.role == SchoolMembership.Role.ADMIN:
        return

    if membership.role == SchoolMembership.Role.PARENT:
        if not parent_has_link_to_student(request.user, student.pk):
            raise ValidationError(
                'No verified link to this student. Redeem a school-issued linking code.'
            )
        return

    if membership.role != SchoolMembership.Role.TEACHER:
        raise ValidationError('You do not have permission to view these results.')

    enrollment = (
        Enrollment.objects.filter(
            student_id=student.pk,
            term_id=term.pk if hasattr(term, 'pk') else term,
            status=Enrollment.Status.ACTIVE,
        )
        .only('class_level_id', 'arm_id', 'term_id')
        .first()
    )
    if enrollment is None:
        raise ValidationError(
            'Student has no active enrollment for this term.'
        )

    from academics.models import ClassSubjectAssignment

    has_any = ClassSubjectAssignment.objects.filter(
        teacher_id=request.user.pk,
        class_level_id=enrollment.class_level_id,
        arm_id=enrollment.arm_id,
        term_id=enrollment.term_id,
    ).exists()
    if not has_any:
        raise ValidationError(
            'You are not assigned to teach this student\'s class/arm/term.'
        )


def _ids(value):
    return value.pk if hasattr(value, 'pk') else value


def _parent_users_for_student(student_id):
    """Users linked to this student through Guardian. Skips unclaimed profiles."""
    from academics.models import StudentGuardianLink

    links = (
        StudentGuardianLink.objects.filter(
            student_id=student_id,
            guardian__user__isnull=False,
        )
        .select_related('guardian__user')
        .order_by('guardian_id')
    )
    users = []
    seen = set()
    for link in links:
        user = link.guardian.user
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        users.append(user)
    return users


def _queue_result_published_notifications(summary_ids):
    """
    Queue email and WhatsApp for each linked parent of these summaries.

    Called from ``transaction.on_commit`` after the publish write commits,
    so ``send_*`` inserts its NotificationLog outside that transaction and
    the worker cannot start before the log row commits. One recipient
    failure is logged and skipped; it does not roll back publication and
    does not stop the other parents.
    """
    from communications.email_service import EmailNotificationService
    from communications.whatsapp_service import WhatsAppNotificationService

    email = EmailNotificationService()
    whatsapp = WhatsAppNotificationService()
    summaries = (
        TermResultSummary.objects.select_related('student', 'term')
        .filter(pk__in=summary_ids, is_published=True)
        .order_by('pk')
    )
    for summary in summaries:
        for parent in _parent_users_for_student(summary.student_id):
            for send in (
                email.send_result_published,
                whatsapp.send_result_published,
            ):
                try:
                    send(summary, parent)
                except Exception:
                    logger.exception(
                        'Could not queue result_published notification '
                        'for summary %s recipient %s',
                        summary.pk,
                        parent.pk,
                    )


def publish_class_term_results(*, class_level, arm, term):
    """
    Publish every TermResultSummary for the active class arm in this term.

    Sets ``is_published`` and ``published_at`` on each existing summary.
    Parents of a summary that was not already published are notified once,
    on commit, via email and WhatsApp. Publishing again refreshes
    ``published_at`` and does not queue another notification.

    Students with no summary yet are counted and left alone — recompute
    first. An empty class, or a class with no summaries at all, is an error.
    """
    class_level_id = _ids(class_level)
    arm_id = _ids(arm)
    term_id = _ids(term)

    student_ids = list(
        Enrollment.objects.filter(
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            status=Enrollment.Status.ACTIVE,
        ).values_list('student_id', flat=True)
    )
    if not student_ids:
        raise ValidationError(
            'No active enrollments for this class, arm, and term.'
        )

    now = timezone.now()
    with transaction.atomic():
        summaries = list(
            TermResultSummary.objects.select_for_update()
            .filter(student_id__in=student_ids, term_id=term_id)
            .order_by('pk')
        )
        if not summaries:
            raise ValidationError(
                'No TermResultSummary rows for this class. '
                'Run POST /api/assessment/results/recompute/ before publishing.'
            )
        notify_ids = [row.pk for row in summaries if not row.is_published]
        for row in summaries:
            row.is_published = True
            row.published_at = now
        TermResultSummary.objects.bulk_update(
            summaries,
            ['is_published', 'published_at'],
        )
        if notify_ids:
            # robust=True: a broker error must not turn a committed publish
            # into an HTTP 500. Per-recipient errors are logged inside.
            transaction.on_commit(
                lambda ids=tuple(notify_ids): _queue_result_published_notifications(ids),
                robust=True,
            )
        published_ids = [row.pk for row in summaries]
        summarized_student_ids = {row.student_id for row in summaries}

    fresh = list(
        TermResultSummary.objects.select_related('student', 'term')
        .filter(pk__in=published_ids)
        .order_by('class_position', 'student__last_name', 'student_id')
    )
    return {
        'class_level_id': class_level_id,
        'arm_id': arm_id,
        'term_id': term_id,
        'published_count': len(fresh),
        'newly_published_count': len(notify_ids),
        'students_without_summary': len(set(student_ids) - summarized_student_ids),
        'published_at': now,
        'summaries': fresh,
    }
