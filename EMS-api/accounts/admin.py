from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin as DjangoTOTPDeviceAdmin
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ('email',)
    list_display = (
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_platform_admin',
        'is_active',
        'date_joined',
    )
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_platform_admin', 'is_active', 'is_superuser')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_platform_admin',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
            },
        ),
    )

    # Email replaces username.
    filter_horizontal = ('groups', 'user_permissions')


_TOTP_SECRET_FIELDS = frozenset({'key', 'qrcode_link'})


class TOTPDeviceAdmin(DjangoTOTPDeviceAdmin):
    """
    Public-schema authenticator devices.

    The stock django-otp admin adds a QR link to the changelist unless
    OTP_ADMIN_HIDE_SENSITIVE_DATA is set. That link renders the shared secret.
    """

    def get_list_display(self, request):
        return ('user', 'name', 'confirmed', 'created_at', 'last_used_at')

    def get_fieldsets(self, request, obj=None):
        fieldsets = []
        for title, options in super().get_fieldsets(request, obj):
            fields = tuple(
                field
                for field in options.get('fields', ())
                if field not in _TOTP_SECRET_FIELDS
            )
            if not fields:
                continue
            fieldsets.append((title, {**options, 'fields': fields}))
        return fieldsets


admin.site.unregister(TOTPDevice)
admin.site.register(TOTPDevice, TOTPDeviceAdmin)
