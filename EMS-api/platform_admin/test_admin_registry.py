"""Every concrete EMS model is on the default Django admin."""

from django.apps import apps
from django.contrib import admin
from django.test import SimpleTestCase

from django_otp.plugins.otp_totp.models import TOTPDevice

from platform_admin.models import WebhookLog

# Public schema: accounts, platform_admin, otp_totp.
# Tenant schema: the rest. django-tenants only shows those when the
# connection schema is that school; registration itself is global.
_APP_LABELS = (
    'accounts',
    'platform_admin',
    'memberships',
    'academics',
    'assessment',
    'attendance',
    'finance',
    'communications',
)

_SECRET_LIST_COLUMNS = frozenset({
    'password',
    'key',
    'qrcode_link',
})


class AdminRegistryTests(SimpleTestCase):
    def test_concrete_models_are_registered(self):
        missing = []
        for label in _APP_LABELS:
            for model in apps.get_app_config(label).get_models():
                if not admin.site.is_registered(model):
                    missing.append(model._meta.label)
        self.assertEqual(missing, [])
        self.assertTrue(admin.site.is_registered(TOTPDevice))

    def test_changelists_do_not_show_secrets(self):
        leaked = []
        for model, model_admin in admin.site._registry.items():
            if model._meta.app_label not in _APP_LABELS and model is not TOTPDevice:
                continue
            columns = model_admin.get_list_display(None)
            for column in columns:
                if column in _SECRET_LIST_COLUMNS:
                    leaked.append(f'{model._meta.label}.{column}')
        self.assertEqual(leaked, [])

        totp_admin = admin.site._registry[TOTPDevice]
        field_names = []
        for _title, options in totp_admin.get_fieldsets(None, obj=object()):
            field_names.extend(options['fields'])
        self.assertNotIn('key', field_names)
        self.assertNotIn('qrcode_link', field_names)

        webhook_admin = admin.site._registry[WebhookLog]
        self.assertNotIn('payload', webhook_admin.get_list_display(None))
        self.assertIn(
            'payload',
            [
                field
                for _title, options in webhook_admin.get_fieldsets(None)
                for field in options['fields']
            ],
        )
