"""
Reusable parent ↔ student link checks for later student-scoped endpoints.

Source of truth after Prompt 5: an active ``StudentGuardianLink`` whose
``Guardian.user`` is the parent. Redeemed ``StudentLinkingCode`` rows remain
an audit trail of how the link was established.
"""

from rest_framework.permissions import BasePermission

from academics.models import Student, StudentGuardianLink
from memberships.models import SchoolMembership
from memberships.permissions import IsParent, resolve_request_membership


def linked_student_ids_for_parent(user):
    """
    Return a set of student UUIDs this parent may access via Guardian links.

    Parents with no Guardian / no StudentGuardianLink get an empty set —
    no information leakage about which students exist.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return set()
    return set(
        StudentGuardianLink.objects.filter(
            guardian__user_id=user.pk,
        ).values_list('student_id', flat=True)
    )


def parent_has_link_to_student(user, student_id):
    """True if ``user`` has a StudentGuardianLink to ``student_id``."""
    if user is None or student_id is None:
        return False
    return StudentGuardianLink.objects.filter(
        guardian__user_id=user.pk,
        student_id=student_id,
    ).exists()


def filter_queryset_for_parent_student_access(queryset, user, *, student_field='pk'):
    """
    Restrict a Student (or student-FK) queryset to those linked to ``user``.

    Usage (later phases)::

        qs = filter_queryset_for_parent_student_access(Student.objects.all(), request.user)
        # or for related models:
        qs = filter_queryset_for_parent_student_access(
            Attendance.objects.all(), request.user, student_field='student_id'
        )
    """
    linked = linked_student_ids_for_parent(user)
    if not linked:
        return queryset.none()
    return queryset.filter(**{f'{student_field}__in': linked})


class HasLinkedStudentAccess(BasePermission):
    """
    Parent may access an object only when a Guardian link exists for that student.

    Expects the view to expose ``get_student_id(obj)`` OR the object to have
    ``student_id`` / ``pk`` (when the object *is* a Student). Non-parents fall
    through as denied here — compose with role permissions on the view.
    """

    message = 'No verified link to this student. Redeem a school-issued linking code.'

    def has_permission(self, request, view):
        # List/create still require an active parent membership; object checks
        # enforce per-student linkage.
        if not IsParent().has_permission(request, view):
            self.message = IsParent.message
            return False
        return True

    def has_object_permission(self, request, view, obj):
        membership = resolve_request_membership(request)
        if membership is None or membership.role != SchoolMembership.Role.PARENT:
            return False

        student_id = None
        get_student_id = getattr(view, 'get_student_id', None)
        if callable(get_student_id):
            student_id = get_student_id(obj)
        elif isinstance(obj, Student):
            student_id = obj.pk
        elif getattr(obj, 'student_id', None) is not None:
            student_id = obj.student_id
        elif hasattr(obj, 'pk'):
            student_id = obj.pk

        return parent_has_link_to_student(request.user, student_id)
