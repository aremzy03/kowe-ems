"""
Daily attendance upsert, term summaries (compute-on-read), and auth helpers.

Bulk entry is idempotent on (student, date): identical retries return the
existing row without rewriting, so AttendanceAuditLog signals skip no-ops.
Permission uses ClassTeacherAssignment helpers — not ClassSubjectAssignment.

Termly attendance is computed on read from DailyAttendance (not materialized):
percentage does not need cross-student comparison the way class ranking does,
and report-card / parent reads are low-frequency.

Parent reads use StudentGuardianLink (academics.parent_access), matching
Phase 2 report-card enforcement. Admin overview surfaces per-class mark-entry
status for a date or term (dashboard pending-register visibility).
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q

from academics.class_teacher_assignments import teacher_is_class_teacher
from academics.models import Enrollment, Student, Term
from attendance.models import DailyAttendance
from memberships.models import SchoolMembership
from memberships.permissions import resolve_request_membership


def enrollment_for_attendance_scope(*, student, class_level_id, arm_id, term_id):
    """
    Active enrollment placing ``student`` in this class/arm/term.

    Returns None when missing (caller turns that into a ValidationError).
    """
    return (
        Enrollment.objects.filter(
            student_id=student.pk if hasattr(student, 'pk') else student,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            status=Enrollment.Status.ACTIVE,
        )
        .select_related('arm', 'class_level', 'term', 'session')
        .first()
    )


def assert_actor_may_mark_attendance(
    *,
    request,
    student,
    class_level_id,
    arm_id,
    term_id,
    attendance_date,
):
    """
    Admin: any enrolled student in the tenant.
    Teacher: must be ClassTeacherAssignment for class/arm/term.

    Also requires an active enrollment matching the register scope and that
    ``attendance_date`` falls within the term's calendar window.
    """
    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    enrollment = enrollment_for_attendance_scope(
        student=student,
        class_level_id=class_level_id,
        arm_id=arm_id,
        term_id=term_id,
    )
    if enrollment is None:
        raise ValidationError(
            {
                'student_id': (
                    'Student has no active enrollment for this class/arm/term.'
                )
            }
        )

    term = enrollment.term
    if attendance_date < term.start_date or attendance_date > term.end_date:
        raise ValidationError(
            {
                'date': (
                    f'Date {attendance_date} is outside term window '
                    f'{term.start_date}–{term.end_date}.'
                )
            }
        )

    if membership.role == SchoolMembership.Role.ADMIN:
        return enrollment

    if membership.role != SchoolMembership.Role.TEACHER:
        raise ValidationError(
            'Only school admins or assigned class teachers may mark attendance.'
        )

    if not teacher_is_class_teacher(
        request.user,
        class_level_id=class_level_id,
        arm_id=arm_id,
        term_id=term_id,
    ):
        raise ValidationError(
            'You are not the assigned class teacher for this class/arm/term. '
            'Ask a school admin to create a ClassTeacherAssignment.'
        )
    return enrollment


def normalize_remarks(remarks):
    """Treat None / blank as empty string for idempotent comparison."""
    if remarks is None:
        return ''
    return str(remarks)


@transaction.atomic
def upsert_daily_attendance(
    *,
    student,
    class_level,
    arm,
    term,
    attendance_date,
    status,
    marked_by,
    remarks='',
):
    """
    Create or update DailyAttendance for (student, date).

    Idempotent: same status + remarks returns the existing row without
    rewriting (so audit signals do not fire a no-op change).

    Returns ``(attendance_obj, created, changed)``.
    """
    valid_statuses = {c.value for c in DailyAttendance.Status}
    status = str(status)
    if status not in valid_statuses:
        raise ValidationError(
            {
                'status': (
                    f'Invalid status {status!r}. '
                    f'Choose one of: {", ".join(sorted(valid_statuses))}.'
                )
            }
        )
    remarks = normalize_remarks(remarks)

    existing = (
        DailyAttendance.objects.select_for_update()
        .filter(student_id=student.pk, date=attendance_date)
        .first()
    )
    if existing is not None:
        if (
            existing.status == status
            and normalize_remarks(existing.remarks) == remarks
        ):
            return existing, False, False
        existing.status = status
        existing.remarks = remarks
        existing.marked_by = marked_by
        existing.class_level = class_level
        existing.arm = arm
        existing.term = term
        existing.full_clean()
        existing.save()
        return existing, False, True

    try:
        with transaction.atomic():
            obj = DailyAttendance(
                student=student,
                class_level=class_level,
                arm=arm,
                term=term,
                date=attendance_date,
                status=status,
                marked_by=marked_by,
                remarks=remarks,
            )
            obj.full_clean()
            obj.save()
            return obj, True, True
    except IntegrityError:
        existing = DailyAttendance.objects.select_for_update().get(
            student_id=student.pk,
            date=attendance_date,
        )
        if (
            existing.status == status
            and normalize_remarks(existing.remarks) == remarks
        ):
            return existing, False, False
        existing.status = status
        existing.remarks = remarks
        existing.marked_by = marked_by
        existing.class_level = class_level
        existing.arm = arm
        existing.term = term
        existing.full_clean()
        existing.save()
        return existing, False, True


# ---------------------------------------------------------------------------
# Termly summary (compute-on-read) + class register grid
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TermAttendanceSummaryData:
    """
    Per-student term attendance aggregate computed from DailyAttendance.

    Not a Django model — deliberately compute-on-read (see playbook Prompt 3).
    ``available`` is False when the student has zero marks for the term so
    consumers (report cards) do not show misleading all-zero absences.
    """

    student_id: str
    term_id: str
    days_present: int
    days_absent: int
    days_late: int
    days_excused: int
    days_marked: int
    total_school_days: int | None
    attendance_percentage: Decimal | None
    available: bool
    message: str

    def as_dict(self) -> dict:
        payload = asdict(self)
        pct = self.attendance_percentage
        payload['attendance_percentage'] = (
            str(pct) if pct is not None else None
        )
        return payload


def _percentage(days_present: int, total_school_days: int | None) -> Decimal | None:
    """
    present / total_school_days × 100, half-up to 2 dp.

    Only ``present`` counts in the numerator (late / excused / absent are
    reported separately). Returns None when the admin has not set a positive
    ``Term.total_school_days``.
    """
    if total_school_days is None or total_school_days <= 0:
        return None
    return (
        Decimal(days_present) * Decimal(100) / Decimal(total_school_days)
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def compute_term_attendance_summary(
    *,
    student: Student | str,
    term: Term | str,
) -> TermAttendanceSummaryData:
    """
    Aggregate DailyAttendance for one student+term on the fly.

    Denominator is ``Term.total_school_days`` (admin-set). If the student has
    no attendance rows for the term, ``available=False`` so UI/PDF can show
    "not available" instead of zeros.
    """
    student_id = student.pk if hasattr(student, 'pk') else student
    if hasattr(term, 'pk'):
        term_obj = term
        term_id = term.pk
    else:
        term_obj = Term.objects.filter(pk=term).first()
        term_id = term
        if term_obj is None:
            raise ValidationError({'term': 'Term not found.'})

    total_school_days = term_obj.total_school_days

    counts = (
        DailyAttendance.objects.filter(student_id=student_id, term_id=term_id)
        .aggregate(
            days_present=Count(
                'id', filter=Q(status=DailyAttendance.Status.PRESENT)
            ),
            days_absent=Count(
                'id', filter=Q(status=DailyAttendance.Status.ABSENT)
            ),
            days_late=Count(
                'id', filter=Q(status=DailyAttendance.Status.LATE)
            ),
            days_excused=Count(
                'id', filter=Q(status=DailyAttendance.Status.EXCUSED)
            ),
            days_marked=Count('id'),
        )
    )
    days_present = counts['days_present'] or 0
    days_absent = counts['days_absent'] or 0
    days_late = counts['days_late'] or 0
    days_excused = counts['days_excused'] or 0
    days_marked = counts['days_marked'] or 0

    if days_marked == 0:
        return TermAttendanceSummaryData(
            student_id=str(student_id),
            term_id=str(term_id),
            days_present=0,
            days_absent=0,
            days_late=0,
            days_excused=0,
            days_marked=0,
            total_school_days=total_school_days,
            attendance_percentage=None,
            available=False,
            message=(
                'Attendance data not available — no daily marks recorded '
                'for this student in this term.'
            ),
        )

    return TermAttendanceSummaryData(
        student_id=str(student_id),
        term_id=str(term_id),
        days_present=days_present,
        days_absent=days_absent,
        days_late=days_late,
        days_excused=days_excused,
        days_marked=days_marked,
        total_school_days=total_school_days,
        attendance_percentage=_percentage(days_present, total_school_days),
        available=True,
        message='',
    )


def assert_actor_may_view_attendance(
    *,
    request,
    student=None,
    class_level_id=None,
    arm_id=None,
    term_id=None,
):
    """
    Admin: any scope.
    Teacher: must be ClassTeacherAssignment for the scope.
    Parent: only when ``student`` is linked via StudentGuardianLink
    (same enforcement as Phase 2 report-card access).

    When ``student`` is given without explicit class/arm, resolve from active
    enrollment for ``term_id`` (teachers). Parents do not need class/arm.
    """
    from academics.parent_access import parent_has_link_to_student

    membership = resolve_request_membership(request)
    if membership is None:
        raise ValidationError('Active membership at this school is required.')

    if membership.role == SchoolMembership.Role.ADMIN:
        return membership

    if membership.role == SchoolMembership.Role.PARENT:
        if student is None:
            raise ValidationError(
                'student is required for parent attendance access.'
            )
        student_id = student.pk if hasattr(student, 'pk') else student
        if not parent_has_link_to_student(request.user, student_id):
            raise ValidationError(
                'No verified link to this student. Redeem a school-issued linking code.'
            )
        return membership

    if membership.role != SchoolMembership.Role.TEACHER:
        raise ValidationError(
            'Only school admins, assigned class teachers, or linked parents '
            'may view attendance.'
        )

    if student is not None and (class_level_id is None or arm_id is None):
        if term_id is None:
            raise ValidationError('term_id is required to resolve student scope.')
        enrollment = (
            Enrollment.objects.filter(
                student_id=student.pk if hasattr(student, 'pk') else student,
                term_id=term_id,
                status=Enrollment.Status.ACTIVE,
            )
            .only('class_level_id', 'arm_id', 'term_id')
            .first()
        )
        if enrollment is None:
            raise ValidationError(
                'Student has no active enrollment for this term.'
            )
        class_level_id = enrollment.class_level_id
        arm_id = enrollment.arm_id
        term_id = enrollment.term_id

    if None in (class_level_id, arm_id, term_id):
        raise ValidationError(
            'class_level, arm, and term are required for teacher attendance access.'
        )

    if not teacher_is_class_teacher(
        request.user,
        class_level_id=class_level_id,
        arm_id=arm_id,
        term_id=term_id,
    ):
        raise ValidationError(
            'You are not the assigned class teacher for this class/arm/term.'
        )
    return membership


def build_admin_attendance_overview(*, overview_date: date | None = None, term=None):
    """
    School-wide attendance mark-entry status for admin dashboards.

    Pass either ``overview_date`` (pending/partial/complete per class for that
    day) or ``term`` (aggregate mark activity across the term). Units are
    class_level+arm+term combinations with active enrollments and/or a
    ClassTeacherAssignment.
    """
    from academics.models import Arm, ClassLevel, ClassTeacherAssignment

    if overview_date is not None and term is not None:
        raise ValidationError('Provide either date or term, not both.')
    if overview_date is None and term is None:
        raise ValidationError('Provide date or term.')

    if overview_date is not None:
        terms = list(
            Term.objects.filter(
                start_date__lte=overview_date,
                end_date__gte=overview_date,
            ).select_related('session')
        )
        if not terms:
            return {
                'mode': 'date',
                'date': overview_date.isoformat(),
                'terms': [],
                'classes': [],
                'summary': {
                    'total_classes': 0,
                    'complete': 0,
                    'partial': 0,
                    'pending': 0,
                    'empty': 0,
                },
                'note': (
                    'No term calendar covers this date — nothing to mark.'
                ),
            }
        term_ids = [t.pk for t in terms]
        term_by_id = {t.pk: t for t in terms}
    else:
        if hasattr(term, 'pk'):
            term_obj = term
        else:
            term_obj = Term.objects.select_related('session').filter(pk=term).first()
            if term_obj is None:
                raise ValidationError({'term': 'Term not found.'})
        terms = [term_obj]
        term_ids = [term_obj.pk]
        term_by_id = {term_obj.pk: term_obj}

    # Scopes: union of active enrollments and form-teacher assignments.
    scopes = {}
    for row in (
        Enrollment.objects.filter(
            term_id__in=term_ids,
            status=Enrollment.Status.ACTIVE,
        )
        .values('class_level_id', 'arm_id', 'term_id')
        .annotate(enrolled_count=Count('id'))
    ):
        key = (row['class_level_id'], row['arm_id'], row['term_id'])
        scopes[key] = {
            'class_level_id': row['class_level_id'],
            'arm_id': row['arm_id'],
            'term_id': row['term_id'],
            'enrolled_count': row['enrolled_count'],
        }

    for row in ClassTeacherAssignment.objects.filter(term_id__in=term_ids).values(
        'class_level_id',
        'arm_id',
        'term_id',
        'teacher_id',
        'teacher__email',
    ):
        key = (row['class_level_id'], row['arm_id'], row['term_id'])
        entry = scopes.setdefault(
            key,
            {
                'class_level_id': row['class_level_id'],
                'arm_id': row['arm_id'],
                'term_id': row['term_id'],
                'enrolled_count': 0,
            },
        )
        entry['class_teacher'] = {
            'id': str(row['teacher_id']),
            'email': row['teacher__email'] or '',
        }

    class_level_ids = {s['class_level_id'] for s in scopes.values()}
    arm_ids = {s['arm_id'] for s in scopes.values()}
    class_names = {
        c.pk: c.name
        for c in ClassLevel.objects.filter(pk__in=class_level_ids).only('id', 'name')
    }
    arm_names = {
        a.pk: a.name for a in Arm.objects.filter(pk__in=arm_ids).only('id', 'name')
    }

    classes_out = []
    if overview_date is not None:
        # Per-scope marked student count for this date.
        marked_rows = (
            DailyAttendance.objects.filter(
                date=overview_date,
                term_id__in=term_ids,
            )
            .values('class_level_id', 'arm_id', 'term_id')
            .annotate(marked_count=Count('id', distinct=True))
        )
        marked_by_scope = {
            (r['class_level_id'], r['arm_id'], r['term_id']): r['marked_count']
            for r in marked_rows
        }

        counts = {'complete': 0, 'partial': 0, 'pending': 0, 'empty': 0}
        for key, scope in sorted(
            scopes.items(),
            key=lambda item: (
                class_names.get(item[0][0], ''),
                arm_names.get(item[0][1], ''),
                str(item[0][2]),
            ),
        ):
            enrolled = scope['enrolled_count']
            marked = marked_by_scope.get(key, 0)
            if enrolled == 0:
                mark_status = 'empty'
            elif marked == 0:
                mark_status = 'pending'
            elif marked >= enrolled:
                mark_status = 'complete'
            else:
                mark_status = 'partial'
            counts[mark_status] += 1
            term_obj = term_by_id[scope['term_id']]
            classes_out.append(
                {
                    'class_level_id': str(scope['class_level_id']),
                    'class_level_name': class_names.get(scope['class_level_id'], ''),
                    'arm_id': str(scope['arm_id']),
                    'arm_name': arm_names.get(scope['arm_id'], ''),
                    'term_id': str(scope['term_id']),
                    'term_name': term_obj.name,
                    'session_name': (
                        term_obj.session.name if term_obj.session_id else ''
                    ),
                    'class_teacher': scope.get('class_teacher'),
                    'enrolled_count': enrolled,
                    'marked_count': marked,
                    'status': mark_status,
                }
            )

        return {
            'mode': 'date',
            'date': overview_date.isoformat(),
            'terms': [
                {
                    'id': str(t.pk),
                    'name': t.name,
                    'session_name': t.session.name if t.session_id else '',
                }
                for t in terms
            ],
            'classes': classes_out,
            'summary': {
                'total_classes': len(classes_out),
                **counts,
            },
            'note': (
                'status=pending means no marks for this date; partial means '
                'some enrolled students unmarked; complete means every enrolled '
                'student has a mark. empty = class/arm with a form teacher but '
                'no active enrollments.'
            ),
        }

    # Term mode: activity aggregates per class/arm.
    term_obj = terms[0]
    day_rows = (
        DailyAttendance.objects.filter(term_id=term_obj.pk)
        .values('class_level_id', 'arm_id')
        .annotate(
            days_with_marks=Count('date', distinct=True),
            marks_total=Count('id'),
            last_marked_date=Max('date'),
        )
    )
    day_by_scope = {
        (r['class_level_id'], r['arm_id']): r for r in day_rows
    }

    pending_never_marked = 0
    empty_scopes = 0
    for key, scope in sorted(
        scopes.items(),
        key=lambda item: (
            class_names.get(item[0][0], ''),
            arm_names.get(item[0][1], ''),
        ),
    ):
        cl_id, arm_id, _tid = key
        stats = day_by_scope.get((cl_id, arm_id), {})
        days_with_marks = stats.get('days_with_marks', 0) or 0
        marks_total = stats.get('marks_total', 0) or 0
        last_marked = stats.get('last_marked_date')
        never_marked = days_with_marks == 0 and scope['enrolled_count'] > 0
        if never_marked:
            pending_never_marked += 1
        if scope['enrolled_count'] == 0:
            empty_scopes += 1
        classes_out.append(
            {
                'class_level_id': str(cl_id),
                'class_level_name': class_names.get(cl_id, ''),
                'arm_id': str(arm_id),
                'arm_name': arm_names.get(arm_id, ''),
                'term_id': str(term_obj.pk),
                'term_name': term_obj.name,
                'session_name': (
                    term_obj.session.name if term_obj.session_id else ''
                ),
                'class_teacher': scope.get('class_teacher'),
                'enrolled_count': scope['enrolled_count'],
                'days_with_marks': days_with_marks,
                'marks_total': marks_total,
                'last_marked_date': (
                    last_marked.isoformat() if last_marked else None
                ),
                'never_marked': never_marked,
            }
        )

    return {
        'mode': 'term',
        'term_id': str(term_obj.pk),
        'term_name': term_obj.name,
        'session_name': term_obj.session.name if term_obj.session_id else '',
        'total_school_days': term_obj.total_school_days,
        'classes': classes_out,
        'summary': {
            'total_classes': len(classes_out),
            'never_marked': pending_never_marked,
            'with_any_marks': sum(
                1 for c in classes_out if c['days_with_marks'] > 0
            ),
            'empty': empty_scopes,
        },
        'note': (
            'Term overview lists class/arm scopes with enrollments and/or a '
            'ClassTeacherAssignment. never_marked flags classes that have '
            'students but zero daily attendance rows this term.'
        ),
    }


def _resolve_register_date_window(*, term: Term, month: str | None, date_from, date_to):
    """
    Resolve [start, end] for the class register grid.

    Prefer explicit date_from/date_to; else month=YYYY-MM clipped to the term
    window; else the full term window.
    """
    window_start = term.start_date
    window_end = term.end_date

    if date_from is not None or date_to is not None:
        if date_from is None or date_to is None:
            raise ValidationError(
                'Provide both date_from and date_to, or neither.'
            )
        if date_to < date_from:
            raise ValidationError({'date_to': 'Must be on or after date_from.'})
        start = max(date_from, window_start)
        end = min(date_to, window_end)
    elif month:
        try:
            year_s, month_s = month.split('-', 1)
            year_i, month_i = int(year_s), int(month_s)
            if not (1 <= month_i <= 12):
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {'month': 'Use YYYY-MM (e.g. 2026-09).'}
            ) from exc
        last_day = monthrange(year_i, month_i)[1]
        start = max(date(year_i, month_i, 1), window_start)
        end = min(date(year_i, month_i, last_day), window_end)
    else:
        start, end = window_start, window_end

    if end < start:
        raise ValidationError(
            'Requested date window does not overlap the term calendar.'
        )
    return start, end


def _iter_weekdays(start: date, end: date):
    """Mon–Fri dates in [start, end]. Weekends omitted (MVP simplification)."""
    current = start
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def build_class_register(
    *,
    class_level_id,
    arm_id,
    term_id,
    month: str | None = None,
    date_from=None,
    date_to=None,
) -> dict:
    """
    Student × date register grid for one class/arm/term.

    Columns are weekdays in the resolved window (Sat/Sun omitted — MVP).
    Cells are status strings or null when unmarked. Students are active
    enrollments for that class/arm/term.
    """
    try:
        term = Term.objects.select_related('session').get(pk=term_id)
    except Term.DoesNotExist as exc:
        raise ValidationError({'term_id': 'Term not found.'}) from exc

    start, end = _resolve_register_date_window(
        term=term,
        month=month,
        date_from=date_from,
        date_to=date_to,
    )
    dates = list(_iter_weekdays(start, end))

    enrollments = list(
        Enrollment.objects.filter(
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            status=Enrollment.Status.ACTIVE,
        )
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )
    students = [
        {
            'id': str(e.student_id),
            'admission_number': e.student.admission_number,
            'name': f'{e.student.last_name}, {e.student.first_name}',
        }
        for e in enrollments
    ]
    student_ids = [e.student_id for e in enrollments]

    marks = {}
    if student_ids and dates:
        for row in DailyAttendance.objects.filter(
            student_id__in=student_ids,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            date__gte=start,
            date__lte=end,
        ).only('student_id', 'date', 'status', 'remarks'):
            marks[(str(row.student_id), row.date.isoformat())] = {
                'status': row.status,
                'remarks': row.remarks,
            }

    grid = []
    for s in students:
        cells = []
        for d in dates:
            key = (s['id'], d.isoformat())
            cell = marks.get(key)
            cells.append(
                {
                    'date': d.isoformat(),
                    'status': cell['status'] if cell else None,
                    'remarks': cell['remarks'] if cell else '',
                }
            )
        grid.append({'student': s, 'cells': cells})

    return {
        'class_level_id': str(class_level_id),
        'arm_id': str(arm_id),
        'term_id': str(term_id),
        'term_name': term.name,
        'session_name': term.session.name if term.session_id else '',
        'date_from': start.isoformat(),
        'date_to': end.isoformat(),
        'total_school_days': term.total_school_days,
        'dates': [d.isoformat() for d in dates],
        'students': students,
        'grid': grid,
        'note': (
            'Register columns are Mon–Fri in the window (weekends omitted). '
            'Attendance % uses Term.total_school_days, not this weekday count.'
        ),
    }
