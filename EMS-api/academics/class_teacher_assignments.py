"""
Reusable form/class-teacher ↔ class/arm/term assignment checks.

Source of truth: ``ClassTeacherAssignment``. Attendance endpoints should
scope teachers through these helpers so only the assigned form teacher
(or a school admin) can mark or edit daily attendance for a class.

Deliberately separate from ``academics.teacher_assignments`` (subject
teachers via ``ClassSubjectAssignment``). A teacher may hold either role,
both, or neither for a given class — they are not linked.
"""

from rest_framework.permissions import BasePermission

from academics.models import ClassTeacherAssignment
from memberships.models import SchoolMembership
from memberships.permissions import (
    IsAdminOrTeacher,
    IsSchoolAdmin,
    IsTeacher,
    resolve_request_membership,
)


def class_teacher_assignments_for_teacher(user):
    """
    QuerySet of ``ClassTeacherAssignment`` rows for ``user``.

    Empty if the user is anonymous / has no class-teacher assignments.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return ClassTeacherAssignment.objects.none()
    return ClassTeacherAssignment.objects.filter(teacher_id=user.pk).select_related(
        'teacher',
        'class_level',
        'arm',
        'term',
        'term__session',
    )


def teacher_is_class_teacher(
    user,
    *,
    class_level_id,
    arm_id,
    term_id,
):
    """
    True if ``user`` is the assigned form/class teacher for this class/arm/term.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if None in (class_level_id, arm_id, term_id):
        return False
    return ClassTeacherAssignment.objects.filter(
        teacher_id=user.pk,
        class_level_id=class_level_id,
        arm_id=arm_id,
        term_id=term_id,
    ).exists()


def filter_queryset_for_class_teacher_assignments(
    queryset,
    user,
    *,
    class_level_field='class_level_id',
    arm_field='arm_id',
    term_field='term_id',
):
    """
    Restrict a queryset to rows matching ``user``'s ClassTeacherAssignments.

    Builds an OR of Q objects for each (class_level, arm, term) tuple the
    teacher owns. Returns ``queryset.none()`` when they have none.
    """
    from django.db.models import Q

    if user is None or not getattr(user, 'is_authenticated', False):
        return queryset.none()

    combos = ClassTeacherAssignment.objects.filter(teacher_id=user.pk).values_list(
        'class_level_id',
        'arm_id',
        'term_id',
    )
    q = Q()
    has_any = False
    for class_level_id, arm_id, term_id in combos:
        has_any = True
        q |= Q(
            **{
                class_level_field: class_level_id,
                arm_field: arm_id,
                term_field: term_id,
            }
        )
    if not has_any:
        return queryset.none()
    return queryset.filter(q)


def get_class_teacher_scope_from_obj(view, obj):
    """
    Resolve (class_level_id, arm_id, term_id) from a view/object.

    Prefer ``view.get_class_teacher_scope(obj)`` when present; otherwise read
    ``class_level_id`` / ``arm_id`` / ``term_id`` (or nested FKs) on the
    object. Returns a 3-tuple; any missing piece is ``None``.
    """
    get_scope = getattr(view, 'get_class_teacher_scope', None)
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
        _attr('class_level_id', 'class_level'),
        _attr('arm_id', 'arm'),
        _attr('term_id', 'term'),
    )


class HasClassTeacherAssignmentAccess(BasePermission):
    """
    Teacher may access an object only when they are its form/class teacher.

    - View-level: requires an active teacher membership.
    - Object-level: checks ``ClassTeacherAssignment`` for the object's scope
      (via ``view.get_class_teacher_scope(obj)`` or standard FK id attributes).

    Compose with ``IsSchoolAdmin`` / ``IsAdminOrTeacher`` when admins should
    bypass — see ``IsAssignedClassTeacherOrAdmin``.
    """

    message = (
        'You are not the assigned class teacher for this class/arm/term. '
        'Ask a school admin to create a ClassTeacherAssignment.'
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

        class_level_id, arm_id, term_id = get_class_teacher_scope_from_obj(view, obj)
        return teacher_is_class_teacher(
            request.user,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
        )


class IsAssignedClassTeacherOrAdmin(BasePermission):
    """
    School admin: full access. Teacher: only their ClassTeacherAssignments.

    Intended for attendance mark/edit endpoints (Phase 3 Prompt 2+). Admins
    skip assignment checks; teachers must match the object's class/arm/term.
    """

    message = 'School admin or assigned class teacher role required.'

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

        class_level_id, arm_id, term_id = get_class_teacher_scope_from_obj(view, obj)
        ok = teacher_is_class_teacher(
            request.user,
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
        )
        if not ok:
            self.message = HasClassTeacherAssignmentAccess.message
        return ok
