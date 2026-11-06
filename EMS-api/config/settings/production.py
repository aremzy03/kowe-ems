"""Production settings."""

from .base import *  # noqa: F401, F403

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

DEBUG = False

# Never reflect arbitrary Origins in production. Set CORS_ALLOWED_ORIGINS
# and/or CORS_ALLOWED_ORIGIN_REGEXES (frontend school subdomains) in env.
CORS_ALLOW_ALL_ORIGINS = False

# Require HTTPS behind CapRover / Traefik / Cloudflare.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
AUTH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=True)  # noqa: F405

# Email: Django's generic SMTP backend. No provider SDK — point EMAIL_HOST
# at whichever transactional service you choose. TLS and SSL are mutually
# exclusive; leave both false only for a local relay on port 25.
# Local settings override EMAIL_BACKEND to the console backend.
EMAIL_BACKEND = env(  # noqa: F405
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = env('EMAIL_HOST', default='localhost')  # noqa: F405
EMAIL_PORT = env.int('EMAIL_PORT', default=25)  # noqa: F405
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')  # noqa: F405
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')  # noqa: F405
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=False)  # noqa: F405
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)  # noqa: F405
EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=30)  # noqa: F405

# WhatsApp Cloud API (Graph). No BSP SDK. Local overrides this to console.
# Leave the token empty until the Utility templates in
# communications/whatsapp_templates.py are approved in WhatsApp Manager.
WHATSAPP_BACKEND = env('WHATSAPP_BACKEND', default='cloud')  # noqa: F405

# Observability: production only. Skip init when SENTRY_DSN is empty.
# traces_sample_rate is a starting value (10%), not a final SLO.
if SENTRY_DSN:  # noqa: F405 — imported via base
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
