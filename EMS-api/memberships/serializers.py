"""Serializers for staff invite create / accept and parent self-signup."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name
from rest_framework import serializers

from memberships.models import SchoolMembership, StaffInvite

User = get_user_model()


class StaffInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=StaffInvite.Role.choices)

    def validate_email(self, value):
        return User.objects.normalize_email(value)

    def validate(self, attrs):
        email = attrs['email']
        if SchoolMembership.objects.filter(user__email__iexact=email, is_active=True).exists():
            raise serializers.ValidationError(
                {'email': 'This email already has an active membership at this school.'}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        # Supersede any earlier pending invite for the same email in this tenant.
        StaffInvite.objects.filter(
            email__iexact=validated_data['email'],
            status=StaffInvite.Status.PENDING,
        ).update(status=StaffInvite.Status.EXPIRED)

        return StaffInvite.objects.create(
            email=validated_data['email'],
            role=validated_data['role'],
            invited_by=request.user,
        )


class StaffInviteSerializer(serializers.ModelSerializer):
    """Response shape after creating an invite (token is not returned to clients)."""

    class Meta:
        model = StaffInvite
        fields = ('id', 'email', 'role', 'status', 'expires_at', 'created_at')
        read_only_fields = fields


class StaffInviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        token = attrs['token']
        try:
            invite = StaffInvite.objects.get(token=token)
        except StaffInvite.DoesNotExist:
            raise serializers.ValidationError(
                {'token': 'Invalid invitation token.'}
            )

        invite.mark_expired_if_needed()

        if invite.status == StaffInvite.Status.ACCEPTED:
            raise serializers.ValidationError(
                {'token': 'This invitation has already been used.'}
            )
        if invite.status == StaffInvite.Status.EXPIRED or invite.is_expired():
            if invite.status != StaffInvite.Status.EXPIRED:
                invite.status = StaffInvite.Status.EXPIRED
                invite.save(update_fields=['status'])
            raise serializers.ValidationError(
                {'token': 'This invitation has expired.'}
            )
        if invite.status != StaffInvite.Status.PENDING:
            raise serializers.ValidationError(
                {'token': 'This invitation is no longer valid.'}
            )

        user = User.objects.filter(email__iexact=invite.email).first()
        if user is None:
            password = attrs.get('password')
            if not password:
                raise serializers.ValidationError(
                    {
                        'password': (
                            'Password is required to create an account for this email.'
                        )
                    }
                )
            validate_password(password, user=User(email=invite.email))
        else:
            if SchoolMembership.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {
                        'token': (
                            'This email already has a membership at this school.'
                        )
                    }
                )

        attrs['invite'] = invite
        attrs['existing_user'] = user
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        # Re-load under row lock so concurrent accepts cannot double-use a token.
        invite = StaffInvite.objects.select_for_update().get(
            pk=self.validated_data['invite'].pk
        )
        invite.mark_expired_if_needed()
        if invite.status != StaffInvite.Status.PENDING:
            raise serializers.ValidationError(
                {'token': 'This invitation is no longer valid.'}
            )

        existing_user = self.validated_data['existing_user']
        created_user = False

        if existing_user is None:
            user = User.objects.create_user(
                email=invite.email,
                password=self.validated_data['password'],
                first_name=self.validated_data.get('first_name') or '',
                last_name=self.validated_data.get('last_name') or '',
            )
            created_user = True
        else:
            user = existing_user
            if SchoolMembership.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {
                        'token': (
                            'This email already has a membership at this school.'
                        )
                    }
                )
            updates = []
            first_name = self.validated_data.get('first_name') or ''
            last_name = self.validated_data.get('last_name') or ''
            if first_name and not user.first_name:
                user.first_name = first_name
                updates.append('first_name')
            if last_name and not user.last_name:
                user.last_name = last_name
                updates.append('last_name')
            if updates:
                user.save(update_fields=updates)

        membership = SchoolMembership.objects.create(
            user=user,
            role=invite.role,
            is_active=True,
        )

        invite.status = StaffInvite.Status.ACCEPTED
        invite.accepted_at = timezone.now()
        invite.save(update_fields=['status', 'accepted_at'])

        return {
            'user': user,
            'membership': membership,
            'invite': invite,
            'created_user': created_user,
        }


class ParentSignupSerializer(serializers.Serializer):
    """
    Public parent self-signup for the current tenant (``X-Tenant-Slug``).

    Creates a shared User when needed and a tenant SchoolMembership with
    role=parent. Does not link any students — that requires linking-code
    redemption in academics.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_email(self, value):
        return User.objects.normalize_email(value)

    def validate(self, attrs):
        if connection.schema_name == get_public_schema_name():
            raise serializers.ValidationError(
                'Parent signup requires a school tenant (X-Tenant-Slug).'
            )

        email = attrs['email']
        password = attrs['password']
        existing = User.objects.filter(email__iexact=email).first()

        if existing is not None:
            if SchoolMembership.objects.filter(user=existing).exists():
                raise serializers.ValidationError(
                    {
                        'email': (
                            'This email already has a membership at this school. '
                            'Please log in instead.'
                        )
                    }
                )
            # Existing shared User (e.g. parent at another school): require the
            # correct password before attaching a parent membership here.
            if not existing.check_password(password):
                raise serializers.ValidationError(
                    {
                        'password': (
                            'Incorrect password for an existing account. '
                            'Log in, or use the password for this email.'
                        )
                    }
                )
            attrs['existing_user'] = existing
        else:
            validate_password(password, user=User(email=email))
            attrs['existing_user'] = None

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        existing = validated_data['existing_user']
        created_user = False

        if existing is None:
            user = User.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                first_name=validated_data.get('first_name') or '',
                last_name=validated_data.get('last_name') or '',
            )
            created_user = True
        else:
            user = existing
            if SchoolMembership.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {
                        'email': (
                            'This email already has a membership at this school. '
                            'Please log in instead.'
                        )
                    }
                )
            updates = []
            first_name = validated_data.get('first_name') or ''
            last_name = validated_data.get('last_name') or ''
            if first_name and not user.first_name:
                user.first_name = first_name
                updates.append('first_name')
            if last_name and not user.last_name:
                user.last_name = last_name
                updates.append('last_name')
            if updates:
                user.save(update_fields=updates)

        membership = SchoolMembership.objects.create(
            user=user,
            role=SchoolMembership.Role.PARENT,
            is_active=True,
        )
        return {
            'user': user,
            'membership': membership,
            'created_user': created_user,
        }
