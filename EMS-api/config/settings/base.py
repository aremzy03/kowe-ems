"""
Shared Django settings for the EMS API.

All secrets and environment-specific values come from environment variables
(via django-environ). Local overrides live in ``local.py``; production
overrides live in ``production.py``.
"""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Read .env from project root when present (local development).
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# django-tenants: schema-per-tenant. ``django_tenants`` must be first in SHARED_APPS.
SHARED_APPS = [
    'django_tenants',
    'platform_admin',
    'accounts',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party (full config in later prompts)
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    # TOTP devices bind to shared User (public schema), not per-tenant.
    'django_otp',
    'django_otp.plugins.otp_totp',
    'corsheaders',
]

# Per-school schema apps. contenttypes stays here (django-tenants standard:
# it is in both SHARED_APPS and TENANT_APPS) and is de-duplicated in INSTALLED_APPS.
TENANT_APPS = [
    'django.contrib.contenttypes',
    'memberships',
    'academics',
    'assessment',
    'attendance',
    'finance',
    'communications',
]

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

# HeaderTenantMiddleware must run first so JWT / X-Tenant-Slug map to a schema
# before SecurityMiddleware or any other middleware touches the DB / tenant.
MIDDLEWARE = [
    'platform_admin.middleware.HeaderTenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TENANT_MODEL = 'platform_admin.Tenant'
TENANT_DOMAIN_MODEL = 'platform_admin.Domain'

# Single-host API: school, platform, and webhook routes share ROOT_URLCONF.
# Schema is selected by HeaderTenantMiddleware (JWT claim / X-Tenant-Slug),
# not by Host. PUBLIC_SCHEMA_URLCONF stays aligned so django-tenants internals
# that still consult it do not 404 platform paths.
PUBLIC_SCHEMA_URLCONF = 'config.urls'
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# UUID PKs will be used on custom models; Django contrib still uses BigAutoField.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Shared identity model (public schema). Roles live on SchoolMembership later.
AUTH_USER_MODEL = 'accounts.User'

# --- Auth / JWT ---
# Access tokens: 15 minutes, returned in JSON, held in frontend memory.
# Refresh tokens: 7 days, httpOnly cookie named ``refresh_token`` (not in JSON).
# Cookie path is /api/auth/ so it is only sent to login/refresh/logout.
#
# AUTH_COOKIE_SECURE: production MUST be True (HTTPS). Local HTTP cannot use
# Secure cookies, so local.py sets this False (override with AUTH_COOKIE_SECURE).
AUTH_REFRESH_COOKIE_NAME = 'refresh_token'
AUTH_REFRESH_COOKIE_PATH = '/api/auth/'
# Strict is correct when the SPA and API are same-site subdomains of one
# parent (schoola.yourapp.com → api.yourapp.com). Cross-site local setups
# (testacademy.localhost → localhost) will not send this cookie; override.
AUTH_REFRESH_COOKIE_SAMESITE = env('AUTH_REFRESH_COOKIE_SAMESITE', default='Strict')
AUTH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=True)
# Host-only when empty (preferred: cookie lives on the API host). Set to
# ``.yourapp.com`` only if you must share the refresh cookie across hosts.
AUTH_COOKIE_DOMAIN = env('AUTH_COOKIE_DOMAIN', default='') or None
# Readable CSRF cookie must be on the parent domain so the SPA on a school
# subdomain can send ``X-CSRFToken`` to the API host. Empty = host-only.
CSRF_COOKIE_DOMAIN = env('CSRF_COOKIE_DOMAIN', default='') or None

# --- CORS ---
# Origins come from CORS_ALLOWED_ORIGINS (comma-separated, no trailing slash).
# Production must keep CORS_ALLOW_ALL_ORIGINS=False and set an explicit list.
# local.py may set CORS_ALLOW_ALL_ORIGINS=True for convenience (credentials
# stay on; django-cors-headers then echoes the request Origin, not "*").
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
# Wildcard frontend subdomains, e.g. ^https://[\\w-]+\\.yourapp\\.com$
CORS_ALLOWED_ORIGIN_REGEXES = env.list('CORS_ALLOWED_ORIGIN_REGEXES', default=[])
# Browser preflight must allow the tenant header.
CORS_ALLOW_HEADERS = (*default_headers, 'x-tenant-slug')

# Cross-origin POSTs to cookie endpoints (refresh/logout) need a trusted
# frontend origin. Django 5 accepts ``https://*.yourapp.com`` wildcards.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Auth brute-force limit: 5/min per IP on login + refresh only (tunable).
# Not applied globally — views set throttle_classes=[AuthEndpointThrottle].
AUTH_THROTTLE_RATE = env('AUTH_THROTTLE_RATE', default='5/min')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # SessionAuthentication is omitted on purpose: it would CSRF-check
    # session-authenticated requests. Bearer JWT APIs stay CSRF-exempt.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'auth': AUTH_THROTTLE_RATE,
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'accounts.serializers.EMSTokenObtainPairSerializer',
    'TOKEN_REFRESH_SERIALIZER': 'accounts.serializers.CookieTokenRefreshSerializer',
}

# --- Celery / Redis ---
# Phase 0 set the broker URL. The app lives in config/celery.py and the
# compose `worker` service runs `celery -A config worker`. Tasks stay off
# the request cycle: do not set CELERY_TASK_ALWAYS_EAGER.
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY', default='')
# Platform-wide commission on online fee payments (percent of each
# transaction retained by the platform account via Paystack subaccount
# percentage_charge). Deliberately NOT settable by school admins.
PLATFORM_COMMISSION_PCT = Decimal(env('PLATFORM_COMMISSION_PCT', default='5.00'))
SENTRY_DSN = env('SENTRY_DSN', default='')

# --- Email / staff invites ---
# Local (config.settings.local) forces the console backend so messages
# print to stdout. Production keeps Django's generic SMTP backend — host,
# port, and credentials are set in config.settings.production from the
# environment. No provider SDK.
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@ems.local')
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
STAFF_INVITE_EXPIRY_DAYS = env.int('STAFF_INVITE_EXPIRY_DAYS', default=7)
# Frontend path on the school subdomain; email link is {frontend-origin}{path}?token=...
STAFF_INVITE_ACCEPT_PATH = env('STAFF_INVITE_ACCEPT_PATH', default='/accept-invite')
# Invite / signup links point at the SPA, not the API host.
# Template may use {slug} (first Domain label) and {domain} (full Domain.domain).
TENANT_FRONTEND_ORIGIN_TEMPLATE = env('TENANT_FRONTEND_ORIGIN_TEMPLATE', default='')
TENANT_FRONTEND_SCHEME = env('TENANT_FRONTEND_SCHEME', default='https')
TENANT_FRONTEND_PORT = env('TENANT_FRONTEND_PORT', default='')

# --- WhatsApp (Meta Cloud API / Graph). No BSP SDK. ---
# Local forces the console backend (prints the template). Production posts
# to Graph when WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are set.
# Templates are submitted by hand; see communications/whatsapp_templates.py.
# Pair limit is 1 message per recipient per 6 seconds (error 131056). The
# queue spaces a bulk enqueue by WHATSAPP_PAIR_INTERVAL_SECONDS.
WHATSAPP_BACKEND = env('WHATSAPP_BACKEND', default='cloud')
WHATSAPP_ACCESS_TOKEN = env('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = env('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_BUSINESS_ACCOUNT_ID = env('WHATSAPP_BUSINESS_ACCOUNT_ID', default='')
WHATSAPP_API_VERSION = env('WHATSAPP_API_VERSION', default='v21.0')
WHATSAPP_API_BASE_URL = env(
    'WHATSAPP_API_BASE_URL', default='https://graph.facebook.com',
)
WHATSAPP_TIMEOUT = env.int('WHATSAPP_TIMEOUT', default=30)
WHATSAPP_PAIR_INTERVAL_SECONDS = env.int(
    'WHATSAPP_PAIR_INTERVAL_SECONDS', default=6,
)

# --- Two-factor auth (TOTP via django-otp) ---
# Short-lived JWT after password for admin/bursar until TOTP succeeds.
# Claim ``ems_purpose=pre_2fa``; full access/refresh tokens are not issued yet.
# Off for now so school admin/bursar get a normal login. Set true to re-enable
# login challenge + confirmed-TOTP gates on admin/bursar endpoints.
REQUIRE_ADMIN_2FA = env.bool('REQUIRE_ADMIN_2FA', default=False)
PRE_2FA_TOKEN_LIFETIME = timedelta(minutes=env.int('PRE_2FA_TOKEN_MINUTES', default=10))
TOTP_DEVICE_NAME = 'default'
# Issuer shown in authenticator apps (otpauth label).
OTP_TOTP_ISSUER = env('OTP_TOTP_ISSUER', default='EMS')
