"""JWT cookie auth views: login, refresh, logout, verify, and TOTP 2FA."""

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from accounts.cookies import clear_refresh_cookie, set_refresh_cookie
from accounts.serializers import (
    CookieTokenRefreshSerializer,
    EMSTokenObtainPairSerializer,
    TwoFactorEnrollConfirmSerializer,
    TwoFactorVerifySerializer,
    build_enroll_payload,
)
from accounts.throttles import AuthEndpointThrottle
from accounts.two_factor import request_uses_pre_2fa_token


class CsrfProtectedAPIMixin:
    """
    DRF marks API views csrf_exempt. Re-enable CsrfViewMiddleware for
    cookie-based endpoints (refresh + logout). JWT Authorization-header
    APIs stay CSRF-exempt via the default DRF as_view() wrapper.
    """

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view.csrf_exempt = False
        return view


def _cookie_token_response(tokens: dict, extra: dict | None = None) -> Response:
    """JSON access (+ extras); refresh goes to httpOnly cookie only."""
    body = {'access': tokens['access']}
    if extra:
        body.update(extra)
    response = Response(body, status=status.HTTP_200_OK)
    set_refresh_cookie(response, tokens['refresh'])
    return response


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CookieTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/login/

    Password step. Teacher/parent: access in JSON + refresh cookie.
    Admin/bursar: no tokens yet — ``requires_2fa`` + ``pre_auth_token``.
    Sets the csrftoken cookie so the SPA can call refresh/logout afterwards.
    """

    serializer_class = EMSTokenObtainPairSerializer
    throttle_classes = [AuthEndpointThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get('requires_2fa'):
            # Pending 2FA: never set refresh cookie or return a full access token.
            return Response(
                {
                    'requires_2fa': True,
                    'enrollment_required': data['enrollment_required'],
                    'pre_auth_token': data['pre_auth_token'],
                    'role': data['role'],
                    'detail': data['detail'],
                },
                status=status.HTTP_200_OK,
            )

        refresh = data.pop('refresh', None)
        # Keep access + role/requires_2fa flags; drop anything else SimpleJWT added.
        body = {
            'access': data['access'],
            'requires_2fa': False,
            'role': data.get('role'),
        }
        response = Response(body, status=status.HTTP_200_OK)
        if refresh:
            set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(CsrfProtectedAPIMixin, TokenRefreshView):
    """
    POST /api/auth/refresh/

    Reads refresh from the ``refresh_token`` cookie. Returns a new access token.
    On rotation, a new refresh token is written to the cookie (not the body).
    CSRF-protected because the credential is a cookie.
    """

    serializer_class = CookieTokenRefreshSerializer
    throttle_classes = [AuthEndpointThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh = response.data.pop('refresh', None)
        if refresh:
            set_refresh_cookie(response, refresh)
        return response


class CookieTokenLogoutView(CsrfProtectedAPIMixin, APIView):
    """
    POST /api/auth/logout/

    Blacklists the current refresh token and clears the cookie.
    CSRF-protected. Access token is not required (cookie is the credential).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)
        clear_refresh_cookie(response)
        return response


class CookieTokenVerifyView(TokenVerifyView):
    """
    POST /api/auth/verify/

    Standard SimpleJWT verification: JSON body ``{"token": "<access or refresh>"}``.
    CSRF-exempt (no cookie credential; token is in the body).
    """


class TwoFactorVerifyView(APIView):
    """
    POST /api/auth/2fa/verify/

    Second login step for admin/bursar who already enrolled TOTP.
    Body: pre_auth_token, totp_code → access + refresh cookie.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthEndpointThrottle]

    def post(self, request, *args, **kwargs):
        serializer = TwoFactorVerifySerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data['tokens']
        membership = serializer.validated_data['membership']
        return _cookie_token_response(
            tokens,
            extra={
                'requires_2fa': False,
                'role': membership.role,
                'detail': 'Two-factor authentication successful.',
            },
        )


class TwoFactorEnrollView(APIView):
    """
    POST /api/auth/2fa/enroll/

    Authenticated (full JWT or pre_2fa Bearer). Returns TOTP secret + QR.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        payload = build_enroll_payload(request.user)
        return Response(payload, status=status.HTTP_200_OK)


class TwoFactorEnrollConfirmView(APIView):
    """
    POST /api/auth/2fa/enroll/confirm/

    Confirms enrollment with a valid authenticator code. When the Bearer token
    is a pre_2fa login token, also issues full access + refresh cookie.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = TwoFactorEnrollConfirmSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data.get('tokens')
        if tokens:
            membership = serializer.validated_data['membership']
            return _cookie_token_response(
                tokens,
                extra={
                    'requires_2fa': False,
                    'enrollment_complete': True,
                    'role': membership.role,
                    'detail': 'Two-factor authentication enrolled.',
                },
            )
        return Response(
            {
                'detail': 'Two-factor authentication enrolled.',
                'enrollment_complete': True,
                'used_pre_2fa_token': request_uses_pre_2fa_token(request),
            },
            status=status.HTTP_200_OK,
        )
