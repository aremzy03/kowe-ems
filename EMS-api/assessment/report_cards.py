"""
Report card PDF generation via WeasyPrint.

Ranks / averages come from materialized ``TermResult`` / ``TermResultSummary``.
Callers must run ``POST /api/assessment/results/recompute/`` first — this
module does not recompute on the fly (same explicit-trigger strategy as
Phase 2 Prompt 4).

Attendance uses compute-on-read ``compute_term_attendance_summary``. Zero
daily marks → "Attendance data not available" rather than misleading zeros.
When marks exist but ``Term.total_school_days`` is unset, counts still render
and attendance % shows as unavailable (no invented calendar).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from academics.models import Enrollment, Student, Term
from assessment.models import (
    AssessmentComponent,
    Score,
    TermResult,
    TermResultSummary,
)
from assessment.services import assert_actor_may_view_student_term_results
from memberships.models import SchoolMembership
from memberships.permissions import resolve_request_membership


@dataclass(frozen=True)
class ReportCardAttendance:
    """Attendance block for the report-card PDF (compute-on-read)."""

    available: bool
    message: str
    days_present: int | None = None
    days_absent: int | None = None
    days_late: int | None = None
    days_excused: int | None = None
    total_school_days: int | None = None
    attendance_percentage: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'available': self.available,
            'message': self.message,
            'days_present': self.days_present,
            'days_absent': self.days_absent,
            'days_late': self.days_late,
            'days_excused': self.days_excused,
            'total_school_days': self.total_school_days,
            'attendance_percentage': self.attendance_percentage,
        }


# Backward-compatible alias for any imports of the Phase 2/3 interim name.
AttendancePlaceholder = ReportCardAttendance

ATTENDANCE_NOT_AVAILABLE = ReportCardAttendance(
    available=False,
    message='Attendance data not available',
)


def get_attendance_summary_for_report(*, student, term) -> ReportCardAttendance:
    """
    Resolve attendance for the report card via compute-on-read summary.

    Never raises on missing attendance helpers. Zero DailyAttendance rows
    → available=False (no misleading all-absent zeros). Percentage is only
    set when the admin has configured ``Term.total_school_days``.
    """
    try:
        from attendance.services import (  # noqa: WPS433
            compute_term_attendance_summary,
        )
    except ImportError:
        return ATTENDANCE_NOT_AVAILABLE

    try:
        summary = compute_term_attendance_summary(student=student, term=term)
    except Exception:
        # Unexpected failure must never 500 report-card generation.
        return ATTENDANCE_NOT_AVAILABLE

    if not summary.available:
        return ReportCardAttendance(
            available=False,
            message=summary.message or 'Attendance data not available',
            total_school_days=summary.total_school_days,
        )

    pct = summary.attendance_percentage
    return ReportCardAttendance(
        available=True,
        message='',
        days_present=summary.days_present,
        days_absent=summary.days_absent,
        days_late=summary.days_late,
        days_excused=summary.days_excused,
        total_school_days=summary.total_school_days,
        attendance_percentage=str(pct) if pct is not None else None,
    )


def _school_name() -> str:
    tenant = getattr(connection, 'tenant', None)
    if tenant is not None and getattr(tenant, 'school_name', None):
        return tenant.school_name
    # ``schema_context`` may set schema_name without attaching a Tenant instance.
    schema = getattr(connection, 'schema_name', None)
    if schema and schema != 'public':
        try:
            from platform_admin.models import Tenant

            name = (
                Tenant.objects.filter(schema_name=schema)
                .values_list('school_name', flat=True)
                .first()
            )
            if name:
                return name
        except Exception:
            pass
    return 'School'


def _ordinal(n: int | None) -> str:
    if n is None:
        return '—'
    # English ordinals for class position (1st, 2nd, 3rd, 4th…).
    if 10 <= (n % 100) <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def build_report_card_context(*, student: Student, term: Term) -> dict[str, Any]:
    """
    Assemble template context from TermResult + TermResultSummary + Scores.

    Raises ``ValidationError`` when no summary exists — PDF ranks require an
    explicit class recompute first.

    This does not check ``is_published``. The parent API refuses the PDF
    until an admin publishes; admin, teacher, and management-command
    renders still include unpublished results.
    """
    summary = (
        TermResultSummary.objects.select_related('student', 'term', 'term__session')
        .filter(student=student, term=term)
        .first()
    )
    if summary is None:
        raise ValidationError(
            'No TermResultSummary for this student/term. '
            'Run POST /api/assessment/results/recompute/ for their class first '
            'so overall average and class position are available on the PDF.'
        )

    enrollment = (
        Enrollment.objects.select_related('class_level', 'arm', 'session')
        .filter(
            student=student,
            term=term,
            status=Enrollment.Status.ACTIVE,
        )
        .first()
    )

    subject_results = list(
        TermResult.objects.select_related('subject')
        .filter(student=student, term=term)
        .order_by('subject__name')
    )

    class_level_id = enrollment.class_level_id if enrollment else None
    components_by_subject: dict[Any, list[AssessmentComponent]] = {}
    if class_level_id is not None and subject_results:
        subject_ids = [r.subject_id for r in subject_results]
        for comp in AssessmentComponent.objects.filter(
            term=term,
            class_level_id=class_level_id,
            subject_id__in=subject_ids,
        ).order_by('name'):
            components_by_subject.setdefault(comp.subject_id, []).append(comp)

    score_map: dict[Any, Decimal] = {}
    component_ids = [
        c.pk for comps in components_by_subject.values() for c in comps
    ]
    if component_ids:
        for sc in Score.objects.filter(
            student=student,
            assessment_component_id__in=component_ids,
        ):
            score_map[sc.assessment_component_id] = sc.score

    subjects_payload = []
    for result in subject_results:
        comps = components_by_subject.get(result.subject_id, [])
        breakdown = []
        for comp in comps:
            raw = score_map.get(comp.pk)
            breakdown.append(
                {
                    'name': comp.name,
                    'weight_percentage': comp.weight_percentage,
                    'max_score': comp.max_score,
                    'score': raw,
                    'score_display': (
                        f'{raw}' if raw is not None else '—'
                    ),
                }
            )
        subjects_payload.append(
            {
                'subject_name': result.subject.name,
                'subject_code': result.subject.code,
                'computed_score': result.computed_score,
                'computed_at': result.computed_at,
                'components': breakdown,
            }
        )

    attendance = get_attendance_summary_for_report(student=student, term=term)

    return {
        'school_name': _school_name(),
        'logo_placeholder': True,
        'generated_at': timezone.now(),
        'student': student,
        'student_name': f'{student.last_name}, {student.first_name}',
        'admission_number': student.admission_number,
        'term': term,
        'term_name': term.name,
        'session_name': term.session.name if term.session_id else '',
        'class_label': (
            f'{enrollment.class_level.name}{enrollment.arm.name}'
            if enrollment is not None
            else '—'
        ),
        'summary': summary,
        'overall_average': summary.overall_average,
        'class_position': summary.class_position,
        'class_position_display': _ordinal(summary.class_position),
        'teacher_remark': summary.teacher_remark or '',
        'admin_remark': summary.admin_remark or '',
        'subjects': subjects_payload,
        'attendance': attendance.as_dict(),
        'recompute_note': (
            'Averages and class position reflect the last explicit recompute '
            f'(summary computed at {summary.computed_at:%Y-%m-%d %H:%M}). '
            'They are not recalculated when this PDF is generated.'
        ),
    }


def render_report_card_html(*, student: Student, term: Term) -> str:
    """Render the report-card HTML template (WeasyPrint input)."""
    context = build_report_card_context(student=student, term=term)
    return render_to_string('assessment/report_card.html', context)


def render_report_card_pdf(*, student: Student, term: Term) -> bytes:
    """
    Render HTML → PDF bytes via WeasyPrint.

    Requires system libraries (Pango, etc.). Import is local so the rest of
    the assessment app still loads if WeasyPrint is missing in a tool env.
    """
    from weasyprint import HTML

    html = render_report_card_html(student=student, term=term)
    return HTML(string=html, base_url=None).write_pdf()


def assert_actor_may_edit_remarks(
    *,
    request,
    student: Student,
    term: Term,
    fields: set[str],
) -> SchoolMembership:
    """
    Teacher: ``teacher_remark`` only, and only for students in an assigned
    class/arm/term (any ClassSubjectAssignment for that class).
    Admin: ``admin_remark`` and/or ``teacher_remark`` for any student.
    """
    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    unknown = fields - {'teacher_remark', 'admin_remark'}
    if unknown:
        raise ValidationError(f'Unknown remark fields: {sorted(unknown)}')
    if not fields:
        raise ValidationError('Provide teacher_remark and/or admin_remark.')

    if membership.role == SchoolMembership.Role.ADMIN:
        return membership

    if membership.role == SchoolMembership.Role.TEACHER:
        if 'admin_remark' in fields:
            raise ValidationError(
                'Only school admins may set admin_remark.'
            )
        # Reuse the same class-scope gate as student result reads.
        assert_actor_may_view_student_term_results(
            request=request,
            student=student,
            term=term,
        )
        return membership

    raise ValidationError('Only school admins or teachers may edit remarks.')


@transaction.atomic
def update_term_result_remarks(
    *,
    student: Student,
    term: Term,
    teacher_remark: str | None = None,
    admin_remark: str | None = None,
) -> TermResultSummary:
    """
    Patch remarks on an existing TermResultSummary.

    Summary must already exist (created by class recompute). Does not invent
    averages/ranks — remarks alone are not enough to mint a summary row.
    """
    summary = (
        TermResultSummary.objects.select_for_update()
        .filter(student=student, term=term)
        .first()
    )
    if summary is None:
        raise ValidationError(
            'No TermResultSummary for this student/term. '
            'Run POST /api/assessment/results/recompute/ for their class first.'
        )
    update_fields = []
    if teacher_remark is not None:
        summary.teacher_remark = teacher_remark
        update_fields.append('teacher_remark')
    if admin_remark is not None:
        summary.admin_remark = admin_remark
        update_fields.append('admin_remark')
    if update_fields:
        summary.save(update_fields=update_fields)
    return summary
