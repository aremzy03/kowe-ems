"""Staff invite API + parent self-signup."""

from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from memberships.emails import send_staff_invite_email
from memberships.permissions import IsSchoolAdmin
from memberships.serializers import (
    ParentSignupSerializer,
    StaffInviteAcceptSerializer,
    StaffInviteCreateSerializer,
    StaffInviteSerializer,
)


class StaffInviteCreateView(APIView):
    """
    POST /api/memberships/invites/

    School-admin only. Creates a pending StaffInvite and emails the accept
    link on the school's frontend subdomain.
    """

    permission_classes = [IsSchoolAdmin]

    def post(self, request, *args, **kwargs):
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
