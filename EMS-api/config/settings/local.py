"""Local development settings."""

from .base import *  # noqa: F401, F403

DEBUG = True

# Single API host (localhost / api.localhost). School UI still uses
# testacademy.localhost:3000; tenant identity is the X-Tenant-Slug header.
_extra_hosts = ['.localhost', 'localhost', '127.0.0.1', 'testserver', 'api.localhost']
ALLOWED_HOSTS = list(dict.fromkeys(list(ALLOWED_HOSTS) + _extra_hosts))  # noqa: F405

# CORS: allow any Origin locally so Next.js (any port / school subdomain)
# can send cookies. django-cors-headers echoes the request Origin (not "*")
# when credentials are on. Production never sets this True. To test the env
# allowlist locally: CORS_ALLOW_ALL_ORIGINS=False plus CORS_ALLOWED_ORIGINS
# / CORS_ALLOWED_ORIGIN_REGEXES in .env.
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=True)  # noqa: F405
_local_cors_regexes = [
    r'^http://localhost:3000$',
    r'^http://127\.0\.0\.1:3000$',
    r'^http://[\w-]+\.localhost:3000$',
    # Platform Next app (separate port from school UI).
    r'^http://localhost:3001$',
    r'^http://127\.0\.0\.1:3001$',
    r'^http://[\w-]+\.localhost:3001$',
]
CORS_ALLOWED_ORIGIN_REGEXES = list(  # noqa: F405
    dict.fromkeys(list(CORS_ALLOWED_ORIGIN_REGEXES) + _local_cors_regexes)  # noqa: F405
)
_local_cors_origins = [
    'http://platform.localhost:3001',
]
CORS_ALLOWED_ORIGINS = list(  # noqa: F405
    dict.fromkeys(list(CORS_ALLOWED_ORIGINS) + _local_cors_origins)  # noqa: F405
)

# SPA origin for CSRF on cookie-based refresh/logout (school + platform UIs).
# Merge with .env so existing lists still gain the local wildcards.
_local_csrf = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://*.localhost:3000',
    'http://localhost:3001',
    'http://127.0.0.1:3001',
    'http://*.localhost:3001',
    'http://platform.localhost:3001',
]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(list(CSRF_TRUSTED_ORIGINS) + _local_csrf))  # noqa: F405

# Cross-site local SPAs (e.g. platform.localhost:3001 → localhost:8000):
# browsers will not send SameSite=Lax/Strict cookies on credentialed POSTs, so
# refresh/logout fail with "CSRF cookie not set". SameSite=None + Secure is
# required; Chromium allows Secure cookies on http://localhost.
# Disable with LOCAL_CROSS_SITE_COOKIES=False if you only use same-site setups.
if env.bool('LOCAL_CROSS_SITE_COOKIES', default=True):  # noqa: F405
    CSRF_COOKIE_SAMESITE = 'None'
    CSRF_COOKIE_SECURE = True
    AUTH_REFRESH_COOKIE_SAMESITE = 'None'  # noqa: F405
    AUTH_COOKIE_SECURE = True
else:
    # Classic local: HTTP without Secure. Cookies only work same-site.
    AUTH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=False)  # noqa: F405

# Invite links → Next.js on the school subdomain, not the API host.
if not TENANT_FRONTEND_ORIGIN_TEMPLATE:  # noqa: F405
    TENANT_FRONTEND_ORIGIN_TEMPLATE = 'http://{slug}.localhost:3000'  # noqa: F405
TENANT_FRONTEND_SCHEME = env('TENANT_FRONTEND_SCHEME', default='http')  # noqa: F405
TENANT_FRONTEND_PORT = env('TENANT_FRONTEND_PORT', default='3000')  # noqa: F405

# Print emails to stdout (staff invites and Phase 5 notifications).
# Production uses Django's generic SMTP backend; see config.settings.production.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Print WhatsApp template payloads to stdout. Production posts to the
# Graph API (WHATSAPP_BACKEND=cloud). No Twilio / 360dialog / BSP SDK.
WHATSAPP_BACKEND = 'console'

# Local-only Paystack stub (Prompt 8). Off unless explicitly enabled.
# HMAC still uses PAYSTACK_SECRET_KEY — set a dummy sk_test_bruno_* value
# when proving signed webhooks without a live Paystack key. Production
# cannot turn this on (DEBUG is False).
PAYSTACK_STUB_GATEWAY = env.bool('PAYSTACK_STUB_GATEWAY', default=False)  # noqa: F405
