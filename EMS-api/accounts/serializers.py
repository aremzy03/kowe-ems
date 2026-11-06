from django.conf import settings
from django.contrib.auth import authenticate
from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from accounts.models import User
from accounts.two_factor import (
    create_unconfirmed_totp_device,
    get_pending_totp_device,
    issue_auth_tokens_for_user,
    mint_pre_2fa_token,
    parse_pre_2fa_token,
    request_uses_pre_2fa_token,
    resolve_login_membership,
    role_requires_2fa,
    stamp_tenant_claims,
    totp_qr_data_uri,
    user_has_confirmed_totp,
    verify_user_totp,
)


class UserSerializer(serializers.ModelSerializer):
    """Basic user identity serializer (shared/public schema)."""

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name')
        read_only_fields = ('id', 'email', 'first_name', 'last_name')


def serialize_me(user, membership=None) -> dict:
    """
    Current user + school (or platform) context for GET /api/auth/me/.

    Reuses ``UserSerializer`` for identity fields. Tenant comes from the
    same ``connection.tenant`` the rest of the API uses (HeaderTenantMiddleware).
    """
    from django.db import connection
    from django_tenants.utils import get_public_schema_name

    from platform_admin.tenancy import tenant_slug_for

    payload = dict(UserSerializer(user).data)
    public = connection.schema_name == get_public_schema_name()
    tenant = getattr(connection, 'tenant', None)

    if membership is not None:
        payload['role'] = membership.role
        payload['membership_id'] = membership.pk
        payload['is_active'] = membership.is_active
    elif getattr(user, 'is_platform_admin', False) and public:
        payload['role'] = 'platform_admin'
        payload['membership_id'] = None
        payload['is_active'] = True
    else:
        payload['role'] = None
        payload['membership_id'] = None
        payload['is_active'] = False

    payload['tenant_schema'] = connection.schema_name
    if public:
        payload['tenant_slug'] = None
        payload['school_name'] = None
        return payload

    if tenant is not None and hasattr(tenant, 'domains'):
        payload['tenant_slug'] = tenant_slug_for(tenant)
    else:
        payload['tenant_slug'] = connection.schema_name.replace('_', '-')
    payload['school_name'] = getattr(tenant, 'school_name', None) or None
    return payload


class MeSerializer(UserSerializer):
    """Documented shape of GET /api/auth/me/ (identity + tenant context)."""

    role = serializers.CharField(read_only=True, allow_null=True)
    membership_id = serializers.UUIDField(read_only=True, allow_null=True)
    is_active = serializers.BooleanField(read_only=True)
    tenant_schema = serializers.CharField(read_only=True)
    tenant_slug = serializers.CharField(read_only=True, allow_null=True)
    school_name = serializers.CharField(read_only=True, allow_null=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'role',
            'membership_id',
            'is_active',
            'tenant_schema',
            'tenant_slug',
            'school_name',
        )


class EMSTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Password login with optional tenant-aware 2FA gating.

    Resolves SchoolMembership in the current tenant schema (from JWT claim or
    ``X-Tenant-Slug``). When ``REQUIRE_ADMIN_2FA`` is on, admin and bursar
    receive a pre_2fa token instead of full JWTs until TOTP succeeds.
    Otherwise every school role receives tokens immediately after password.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # TODO: set school_id from SchoolMembership once multi-membership
        # handling is decided (a user may belong to multiple tenants).
        stamp_tenant_claims(token, user)
        return token

    def validate(self, attrs):
        # Authenticate without issuing tokens yet — we may need the 2FA branch.
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            'password': attrs['password'],
        }
        request = self.context.get('request')
        if request is not None:
            authenticate_kwargs['request'] = request

        user = authenticate(**authenticate_kwargs)
        if user is None or not user.is_active:
            raise AuthenticationFailed(
                'No active account found with the given credentials.',
                code='no_active_account',
            )

        self.user = user
        membership = resolve_login_membership(user)
        if membership is None:
            # Platform operators have no SchoolMembership. They authenticate
            # on the public schema only (User.is_platform_admin, no tenant
            # header). School requests still require an active membership.
            if (
                getattr(user, 'is_platform_admin', False)
                and connection.schema_name == get_public_schema_name()
            ):
                data = super().validate(attrs)
                data['role'] = 'platform_admin'
                data['requires_2fa'] = False
                return data
            raise AuthenticationFailed(
                'No active membership at this school.',
                code='no_membership',
            )

        if not role_requires_2fa(membership.role):
            data = super().validate(attrs)
            data['role'] = membership.role
            data['requires_2fa'] = False
            return data

        enrollment_required = not user_has_confirmed_totp(user)
        return {
            'requires_2fa': True,
            'enrollment_required': enrollment_required,
            'pre_auth_token': mint_pre_2fa_token(user),
            'role': membership.role,
            'detail': (
                'Two-factor authentication enrollment required.'
                if enrollment_required
                else 'Two-factor authentication code required.'
            ),
        }


class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    """Read the refresh token from the httpOnly cookie, not the JSON body."""

    refresh = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        cookie_token = None
        if request is not None:
            cookie_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not cookie_token:
            raise InvalidToken('No valid refresh token found in cookie.')
        attrs['refresh'] = cookie_token
        return super().validate(attrs)


class TwoFactorVerifySerializer(serializers.Serializer):
    """Complete admin/bursar login: pre_auth_token + TOTP code → full JWTs."""

    pre_auth_token = serializers.CharField()
    totp_code = serializers.CharField(min_length=6, max_length=8, trim_whitespace=True)

    def validate(self, attrs):
        token = parse_pre_2fa_token(attrs['pre_auth_token'])
        try:
            user_id = token['user_id']
        except KeyError as exc:
            raise InvalidToken('Invalid pre-auth token payload.') from exc

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'pre_auth_token': 'User not found or inactive.'}
            ) from exc

        if not user_has_confirmed_totp(user):
            raise serializers.ValidationError(
                {
                    'detail': (
                        'Complete 2FA enrollment before verifying a login code. '
                        'POST /api/auth/2fa/enroll/ then /api/auth/2fa/enroll/confirm/.'
                    )
                }
            )

        if not verify_user_totp(user, attrs['totp_code']):
            raise serializers.ValidationError(
                {'totp_code': 'Invalid authentication code.'}
            )

        membership = resolve_login_membership(user)
        if membership is None or not role_requires_2fa(membership.role):
            raise serializers.ValidationError(
                {'detail': 'Two-factor login is not applicable for this membership.'}
            )

        attrs['user'] = user
        attrs['membership'] = membership
        attrs['tokens'] = issue_auth_tokens_for_user(user)
        return attrs


class TwoFactorEnrollConfirmSerializer(serializers.Serializer):
    """Confirm a pending TOTP device with a valid code from the authenticator app."""

    totp_code = serializers.CharField(min_length=6, max_length=8, trim_whitespace=True)
    # Optional: when confirming during the login pre_2fa flow, also mint JWTs.
    issue_tokens = serializers.BooleanField(default=True, required=False)

    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        if not user or not user.is_authenticated:
            raise serializers.ValidationError('Authentication required.')

        if user_has_confirmed_totp(user):
            raise serializers.ValidationError(
                {
                    'detail': (
                        'Two-factor authentication is already enrolled. '
                        'Use POST /api/auth/2fa/verify/ with your existing '
                        'authenticator code. Re-enrollment requires a future '
                        'admin reset flow.'
                    )
                }
            )

        device = get_pending_totp_device(user)
        if device is None:
            raise serializers.ValidationError(
                {
                    'detail': (
                        'No pending enrollment. Call POST /api/auth/2fa/enroll/ first.'
                    )
                }
            )

        if not device.verify_token(attrs['totp_code'].strip()):
            raise serializers.ValidationError(
                {'totp_code': 'Invalid authentication code.'}
            )

        device.confirmed = True
        device.save(update_fields=['confirmed'])

        attrs['user'] = user
        attrs['device'] = device
        attrs['tokens'] = None
        # Issue full tokens only when this request used a pre_2fa Bearer token
        # (first-time enroll during login). Already-sessioned users just confirm.
        if attrs.get('issue_tokens', True) and request_uses_pre_2fa_token(request):
            membership = resolve_login_membership(user)
            if membership is not None and role_requires_2fa(membership.role):
                attrs['tokens'] = issue_auth_tokens_for_user(user)
                attrs['membership'] = membership
        return attrs


def build_enroll_payload(user) -> dict:
    if user_has_confirmed_totp(user):
        raise serializers.ValidationError(
            {
                'detail': (
                    'Two-factor authentication is already enrolled. '
                    'Use POST /api/auth/2fa/verify/ with your existing '
                    'authenticator code. Re-enrollment requires a future '
                    'admin reset flow.'
                )
            }
        )
    device = create_unconfirmed_totp_device(user)
    config_url = device.config_url
    # Authenticator apps expect the base32 secret from the otpauth URI, not
    # django-otp's hex ``device.key``.
    from urllib.parse import parse_qs, urlparse

    secret = parse_qs(urlparse(config_url).query).get('secret', [None])[0]
    return {
        'device_id': device.pk,
        'secret': secret,
        'config_url': config_url,
        'qr_code': totp_qr_data_uri(config_url),
        'issuer': getattr(settings, 'OTP_TOTP_ISSUER', 'EMS'),
        'detail': (
            'Scan the QR code (or enter the secret) in your authenticator app, '
            'then POST the current code to /api/auth/2fa/enroll/confirm/.'
        ),
    }
