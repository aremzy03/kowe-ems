"""Production settings."""

from .base import *  # noqa: F401, F403

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

DEBUG = False

# Never reflect arbitrary Origins in production. Set CORS_ALLOWED_ORIGINS in env.
CORS_ALLOW_ALL_ORIGINS = False

# Require HTTPS behind CapRover / Traefik / Cloudflare.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
AUTH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=True)  # noqa: F405

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
