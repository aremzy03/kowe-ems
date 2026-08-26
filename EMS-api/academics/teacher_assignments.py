"""
Reusable teacher ↔ class/subject/term assignment checks.

Source of truth: ``ClassSubjectAssignment``. Later assessment endpoints
(score entry, broadsheet, report cards) should scope teachers through these
helpers so a teacher never sees or edits marks outside their assignments.

Pattern mirrors ``academics.parent_access`` for parents.
"""

from rest_framework.permissions import BasePermission

from academics.models import ClassSubjectAssignment
from memberships.models import SchoolMembership
from memberships.permissions import (
    IsAdminOrTeacher,
    IsSchoolAdmin,
    IsTeacher,
    resolve_request_membership,
)


def assignments_for_teacher(user):
    """
    QuerySet of ``ClassSubjectAssignment`` rows for ``user``.

    Empty if the user is anonymous / has no assignments.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return ClassSubjectAssignment.objects.none()
    return ClassSubjectAssignment.objects.filter(teacher_id=user.pk).select_related(
        'teacher',
        'subject',
        'class_level',
        'arm',
        'term',
        'term__session',
    )


def teacher_has_assignment(
    user,
    *,
    subject_id,
    class_level_id,
    arm_id,
    term_id,
):
    """
    True if ``user`` is assigned to teach this subject/class/arm/term combo.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if None in (subject_id, class_level_id, arm_id, term_id):
        return False
    return ClassSubjectAssignment.objects.filter(
        teacher_id=user.pk,
        subject_id=subject_id,
        class_level_id=class_level_id,
        arm_id=arm_id,
        term_id=term_id,
    ).exists()


def filter_queryset_for_teacher_assignments(
    queryset,
    user,
    *,
    subject_field='subject_id',
    class_level_field='class_level_id',
    arm_field='arm_id',
    term_field='term_id',
):
    """
    Restrict a queryset to rows matching ``user``'s ClassSubjectAssignments.

    Builds an OR of Q objects for each (subject, class_level, arm, term)
    tuple the teacher owns. Returns ``queryset.none()`` when they have none.

    Usage (Prompts 3 / 5)::

        from academics.teacher_assignments import (
            filter_queryset_for_teacher_assignments,
        )

        qs = filter_queryset_for_teacher_assignments(
            SomeModel.objects.all(),
            request.user,
            subject_field='subject_id',
            class_level_field='class_level_id',
            arm_field='arm_id',
            term_field='term_id',
        )
    """
    from django.db.models import Q

    if user is None or not getattr(user, 'is_authenticated', False):
        return queryset.none()

    combos = ClassSubjectAssignment.objects.filter(teacher_id=user.pk).values_list(
        'subject_id',
        'class_level_id',
        'arm_id',
        'term_id',
    )
    q = Q()
    has_any = False
    for subject_id, class_level_id, arm_id, term_id in combos:
        has_any = True
        q |= Q(
            **{
                subject_field: subject_id,
                class_level_field: class_level_id,
                arm_field: arm_id,
                term_field: term_id,
            }
        )
    if not has_any:
        return queryset.none()
    return queryset.filter(q)


def get_assignment_scope_from_obj(view, obj):
    """
    Resolve (subject_id, class_level_id, arm_id, term_id) from a view/object.

    Prefer ``view.get_assignment_scope(obj)`` when present; otherwise read
    ``subject_id`` / ``class_level_id`` / ``arm_id`` / ``term_id`` (or nested
    FKs) on the object. Returns a 4-tuple; any missing piece is ``None``.
    """
    get_scope = getattr(view, 'get_assignment_scope', None)
    if callable(get_scope):
        return get_scope(obj)

    def _attr(name, fk_name=None):
        value = getattr(obj, name, None)
        if value is not None:
            return value
        if fk_name:
            related = getattr(obj, fk_name, None)
            if related is not None:
                return getattr(related, 'pk', related)
        return None

    return (
        _attr('subject_id', 'subject'),
        _attr('class_level_id', 'class_level'),
        _attr('arm_id', 'arm'),
        _attr('term_id', 'term'),
    )


class HasTeacherAssignmentAccess(BasePermission):
    """
    Teacher may access an object only when assigned to its class/subject/term.

    - View-level: requires an active teacher membership.
    - Object-level: checks ``ClassSubjectAssignment`` for the object's scope
      (via ``view.get_assignment_scope(obj)`` or standard FK id attributes).

    Compose with ``IsSchoolAdmin`` / ``IsAdminOrTeacher`` on the view when
    admins should bypass assignment checks — see
    ``IsAssignedTeacherOrAdmin``.
    """

    message = (
        'You are not assigned to teach this class/subject/term. '
        'Ask a school admin to create a ClassSubjectAssignment.'
    )

    def has_permission(self, request, view):
        if not IsTeacher().has_permission(request, view):
            self.message = IsTeacher.message
            return False
        return True

    def has_object_permission(self, request, view, obj):
        membership = resolve_request_membership(request)
        if membership is None or membership.role != SchoolMembership.Role.TEACHER:
            return False

        subject_id, class_level_id, arm_id, term_id = get_assignment_scope_from_obj(
            view, obj
        )
        return teacher_has_assignment(
            request.user,
            subject_id=subject_id,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
        )


class IsAssignedTeacherOrAdmin(BasePermission):
    """
    School admin: full access. Teacher: only their ClassSubjectAssignments.

    Intended for assessment write/read endpoints in Prompts 3 and 5. Admins
    skip assignment checks; teachers must match the object's scope.
    """

    message = 'School admin or assigned teacher role required.'

    def has_permission(self, request, view):
        if not IsAdminOrTeacher().has_permission(request, view):
            self.message = IsAdminOrTeacher.message
            return False
        return True

    def has_object_permission(self, request, view, obj):
        membership = resolve_request_membership(request)
        if membership is None:
            return False
        if membership.role == SchoolMembership.Role.ADMIN:
            # Admin already passed IsSchoolAdmin's 2FA gate via IsAdminOrTeacher.
            return IsSchoolAdmin().has_permission(request, view)
        if membership.role != SchoolMembership.Role.TEACHER:
            return False

        subject_id, class_level_id, arm_id, term_id = get_assignment_scope_from_obj(
            view, obj
        )
        ok = teacher_has_assignment(
            request.user,
            subject_id=subject_id,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
        )
        if not ok:
            self.message = HasTeacherAssignmentAccess.message
        return ok
