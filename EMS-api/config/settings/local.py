"""Local development settings."""

from .base import *  # noqa: F401, F403

DEBUG = True

# Tenant hosts like testacademy.localhost (django-tenants subdomain routing).
_extra_hosts = ['.localhost', 'localhost', '127.0.0.1', 'testserver']
ALLOWED_HOSTS = list(dict.fromkeys(list(ALLOWED_HOSTS) + _extra_hosts))  # noqa: F405

# CORS: allow any Origin locally so Next.js (any port) can send cookies.
# django-cors-headers echoes the request Origin (not "*") when credentials
# are on. Production never sets this True. To test the env allowlist locally:
# CORS_ALLOW_ALL_ORIGINS=False plus CORS_ALLOWED_ORIGINS in .env.
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=True)  # noqa: F405

# http://localhost cannot persist Secure cookies. Production keeps the base
# default (True). Override with AUTH_COOKIE_SECURE=True to test HTTPS locally.
AUTH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=False)  # noqa: F405

# SPA origin for CSRF on cookie-based refresh/logout (different port is OK).
if not CSRF_TRUSTED_ORIGINS:  # noqa: F405
    CSRF_TRUSTED_ORIGINS = [  # noqa: F405
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]

# Print emails to stdout (staff invite links visible in runserver / manage.py).
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
