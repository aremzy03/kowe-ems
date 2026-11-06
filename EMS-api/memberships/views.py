"""Staff directory, invite inbox, invite accept, and parent self-signup."""

from django.db import connection
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from memberships.emails import send_staff_invite_email
from memberships.models import SchoolMembership, StaffInvite
from memberships.permissions import IsSchoolAdmin
from memberships.serializers import (
    LAST_ADMIN_MESSAGE,
    ParentSignupSerializer,
    SchoolMembershipSerializer,
    StaffInviteAcceptSerializer,
    StaffInviteCreateSerializer,
    StaffInviteSerializer,
    would_remove_last_active_admin,
)


def _query_bool(value):
    """Parse a query-string flag. None if the value is not a recognised bool."""
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in ('1', 'true', 'yes'):
        return True
    if lowered in ('0', 'false', 'no'):
        return False
    return None


class SchoolMembershipViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Tenant-scoped staff directory.

    List / retrieve / PATCH ``role`` and ``is_active``. Create stays on
    invite-accept and parent signup — POST is not allowed here.

    Destroy is a **soft deactivate** (``is_active=false``). Users in the
    public schema are never deleted. PATCH ``is_active=false`` does the
    same thing.

    Default list is staff roles (admin / teacher / bursar). Parents are
    omitted unless ``?role=parent`` (or another explicit ``?role=``).
    """

    serializer_class = SchoolMembershipSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']
    lookup_value_regex = r'[0-9a-f-]{36}'
    queryset = SchoolMembership.objects.select_related('user').all()

    def get_queryset(self):
        qs = SchoolMembership.objects.select_related('user').all()
        role = self.request.query_params.get('role')
        if role:
            if role not in SchoolMembership.Role.values:
                return qs.none()
            qs = qs.filter(role=role)
        elif self.action == 'list':
            qs = qs.filter(role__in=SchoolMembership.STAFF_ROLES)

        is_active = _query_bool(self.request.query_params.get('is_active'))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if would_remove_last_active_admin(instance, new_is_active=False):
            return Response(
                {'detail': LAST_ADMIN_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffInviteViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Staff invite inbox + create.

    POST /api/memberships/invites/ — school-admin only; emails the accept
    link. Token is never returned (see StaffInviteSerializer).

    GET list defaults to pending invites. ``?status=`` selects another
    status. Tokens are never included.

    DELETE revokes a pending invite by setting status=expired (same
    sentinel used when a newer invite supersedes an older pending one).
    """

    serializer_class = StaffInviteSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    lookup_value_regex = r'[0-9a-f-]{36}'
    queryset = StaffInvite.objects.all()

    def get_queryset(self):
        qs = StaffInvite.objects.all()
        if self.action != 'list':
            return qs

        stale = qs.filter(
            status=StaffInvite.Status.PENDING,
            expires_at__lte=timezone.now(),
        )
        if stale.exists():
            stale.update(status=StaffInvite.Status.EXPIRED)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter not in StaffInvite.Status.values:
                return qs.none()
            return qs.filter(status=status_filter)
        return qs.filter(status=StaffInvite.Status.PENDING)

    def create(self, request, *args, **kwargs):
        serializer = StaffInviteCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        invite = serializer.save()

        tenant = getattr(request, 'tenant', None)
        school_name = getattr(tenant, 'school_name', None) or connection.schema_name
        accept_url = send_staff_invite_email(
            request=request,
            invite=invite,
            school_name=school_name,
        )

        data = StaffInviteSerializer(invite).data
        # Local/dev convenience: include the URL so console email can be
        # correlated without scraping stdout. Harmless in production responses.
        data['accept_url'] = accept_url
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        invite = self.get_object()
        invite.mark_expired_if_needed()
        if invite.status != StaffInvite.Status.PENDING:
            return Response(
                {'detail': 'Only pending invitations can be revoked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invite.status = StaffInvite.Status.EXPIRED
        invite.save(update_fields=['status'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffInviteAcceptView(APIView):
    """
    POST /api/memberships/invites/accept/

    Public. Body: token, and password (+ optional names) when the invitee
    does not already have a shared User. Creates SchoolMembership and marks
    the invite accepted. Clear 400s for expired / already-used tokens.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = StaffInviteAcceptSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        membership = result['membership']
        user = result['user']
        return Response(
            {
                'detail': 'Invitation accepted.',
                'created_user': result['created_user'],
                'membership': {
                    'id': str(membership.id),
                    'role': membership.role,
                    'is_active': membership.is_active,
                },
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
            },
            status=status.HTTP_200_OK,
        )


class ParentSignupView(APIView):
    """
    POST /api/memberships/parents/signup/

    Public. Creates a shared User (if needed) and a parent SchoolMembership
    for the current tenant. No student links until a linking code is redeemed.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ParentSignupSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        membership = result['membership']
        user = result['user']
        return Response(
            {
                'detail': 'Parent account created.',
                'created_user': result['created_user'],
                'membership': {
                    'id': str(membership.id),
                    'role': membership.role,
                    'is_active': membership.is_active,
                },
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
            },
            status=status.HTTP_201_CREATED,
        )
