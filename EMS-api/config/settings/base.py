"""
Shared Django settings for the EMS API.

All secrets and environment-specific values come from environment variables
(via django-environ). Local overrides live in ``local.py``; production
overrides live in ``production.py``.
"""

from datetime import timedelta
from pathlib import Path

import environ

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

# TenantMainMiddleware must run first so the request host maps to a schema
# before SecurityMiddleware or any other middleware touches the DB / tenant.
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
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
AUTH_REFRESH_COOKIE_SAMESITE = 'Strict'
AUTH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=True)

# --- CORS ---
# Origins come from CORS_ALLOWED_ORIGINS (comma-separated, no trailing slash).
# Production must keep CORS_ALLOW_ALL_ORIGINS=False and set an explicit list.
# local.py may set CORS_ALLOW_ALL_ORIGINS=True for convenience (credentials
# stay on; django-cors-headers then echoes the request Origin, not "*").
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

# Cross-origin POSTs to cookie endpoints (refresh/logout) need a trusted
# frontend origin. Empty by default; local.py / env should list the SPA.
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

# --- Integrations (values only; wiring comes in later prompts) ---
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY', default='')
SENTRY_DSN = env('SENTRY_DSN', default='')

# --- Email / staff invites ---
# Production should set a real backend + DEFAULT_FROM_EMAIL. Local uses console.
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@ems.local')
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
STAFF_INVITE_EXPIRY_DAYS = env.int('STAFF_INVITE_EXPIRY_DAYS', default=7)
# Frontend path on the tenant host; email link is {tenant-origin}{path}?token=...
STAFF_INVITE_ACCEPT_PATH = env('STAFF_INVITE_ACCEPT_PATH', default='/accept-invite')

# --- Two-factor auth (TOTP via django-otp) ---
# Short-lived JWT after password for admin/bursar until TOTP succeeds.
# Claim ``ems_purpose=pre_2fa``; full access/refresh tokens are not issued yet.
PRE_2FA_TOKEN_LIFETIME = timedelta(minutes=env.int('PRE_2FA_TOKEN_MINUTES', default=10))
TOTP_DEVICE_NAME = 'default'
# Issuer shown in authenticator apps (otpauth label).
OTP_TOTP_ISSUER = env('OTP_TOTP_ISSUER', default='EMS')
