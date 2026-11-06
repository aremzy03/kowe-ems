# EMS Project Initialization — Coding Agent Prompt Playbook

**Purpose:** Phase 0 of the roadmap — scaffold the multi-tenant Django foundation before any feature app is built. Run these prompts in order against your coding agent (Cursor/Claude Code). Each prompt is self-contained but assumes prior prompts have already been applied. Verify each step before moving to the next — this is infrastructure everything else sits on, so mistakes here compound.

---

## Primer — paste this once at the start of the session

```
We're building a multi-tenant SaaS Educational Management System for Nigerian K-12 schools.

Stack: Django 5.2 + Django REST Framework, django-tenants for schema-per-tenant
multi-tenancy, PostgreSQL, djangorestframework-simplejwt for auth, Celery + Redis
for async tasks, deployed via Docker on CapRover with Traefik + Cloudflare DNS.

Architecture: schema-per-tenant multi-tenancy via django-tenants. Subdomain-based
tenant resolution (schoolname.ems.incelgroup.com). One codebase, one database
server, each school gets its own PostgreSQL schema. A shared public schema holds
cross-tenant data (User identity, Tenant/Domain records); each school's schema
holds their academic, assessment, attendance, and finance data.

Follow Django/DRF conventions strictly. Use UUID primary keys on all models.
Write migrations as you go — do not batch them. After each prompt, tell me what
you created and any decisions you made that weren't explicitly specified.
```

---



## Prompt 1 — Project scaffold & dependency setup

```
Initialize a new Django 5.2 project called `ems`.

1. Create the project with a `config/` settings package (not a flat settings.py),
   split into settings/base.py, settings/local.py, settings/production.py.
2. Set up dependency management with a requirements.txt (or pyproject.toml if you
   prefer poetry — ask me which before proceeding) containing:
   django, djangorestframework, django-tenants, djangorestframework-simplejwt,
   django-environ, django-cors-headers, celery, redis, psycopg2-binary,
   django-ratelimit, sentry-sdk, pytest-django, python-decouple (optional, only
   if not using django-environ for this)
3. Create a .env.example listing every environment variable the settings files
   will read (DB credentials, SECRET_KEY, DEBUG, ALLOWED_HOSTS, REDIS_URL,
   PAYSTACK_SECRET_KEY, SENTRY_DSN) — do not commit an actual .env.
4. Set up django-environ in settings/base.py to read all config from environment
   variables, no hardcoded secrets anywhere.
5. Do not run any migrations yet — there's no database configuration until the
   next prompt.

Show me the final directory structure when done.
```

---



## Prompt 2 — django-tenants configuration

```
Configure django-tenants for schema-per-tenant multi-tenancy.

1. Set DATABASES['default']['ENGINE'] to 'django_tenants.postgresql_backend'.
2. Add 'django_tenants' to the top of INSTALLED_APPS.
3. Set DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter'].
4. Create a `platform_admin` app (in the shared/public schema) with two models:
   - Tenant(TenantMixin): school_name, schema_name (inherited), is_active,
     created_at
   - Domain(DomainMixin): standard django-tenants domain model
   Set TENANT_MODEL = 'platform_admin.Tenant' and
   TENANT_DOMAIN_MODEL = 'platform_admin.Domain'.
5. Define SHARED_APPS (django_tenants, platform_admin, accounts — accounts app
   comes in the next prompt, just reserve it here — plus django.contrib.admin,
   auth, contenttypes, sessions, staticfiles) and TENANT_APPS (empty list for
   now, we'll populate it in Prompt 4). Confirm INSTALLED_APPS =
   SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS].
6. Add 'django_tenants.middleware.main.TenantMainMiddleware' as the FIRST
   entry in MIDDLEWARE, before SecurityMiddleware is not correct — confirm
   the correct django-tenants-recommended position (it should run very early,
   check current django-tenants docs for exact ordering relative to
   SecurityMiddleware, since this affects schema resolution timing).
7. Do NOT create migrations yet — do that in Prompt 3 once accounts exists.

Explain where TenantMainMiddleware sits relative to SecurityMiddleware and why,
since this affects schema resolution timing before authentication runs.
```

---



## Prompt 3 — Shared accounts app (User model)

```
Create an `accounts` app in the shared/public schema (add it to SHARED_APPS).

1. Custom User model, UUID primary key, extending AbstractBaseUser +
   PermissionsMixin. Fields: email (unique, used as USERNAME_FIELD), first_name,
   last_name, is_active, is_staff, date_joined. No role field here — role
   belongs to per-tenant SchoolMembership, which comes later. This User model
   represents identity only, shared across all tenants.
2. Custom UserManager with create_user and create_superuser.
3. Register in settings: AUTH_USER_MODEL = 'accounts.User'.
4. Basic DRF serializer for user (read-only fields: id, email, first_name,
   last_name) — no auth logic yet, that's Prompt 5.
5. Now generate and apply migrations:
   - python manage.py makemigrations
   - python manage.py migrate_schemas --shared
6. Confirm the public schema now has accounts_user, platform_admin_tenant,
   and platform_admin_domain tables.

Show me the migration output and confirm no errors.
```

---



## Prompt 4 — Tenant app skeletons

```
Create the following Django apps, all going into TENANT_APPS (per-school
schema, NOT shared):

- memberships   (SchoolMembership model: FK to accounts.User, role field
                  with choices admin/teacher/bursar/parent, is_active,
                  joined_at — this is what makes a User a member of THIS
                  school with THIS role)
- academics     (empty app for now — just app config, no models yet)
- assessment    (empty app for now)
- attendance    (empty app for now)
- finance       (empty app for now)
- communications (empty app for now)

Only build out the `memberships` app's SchoolMembership model fully in this
prompt — the rest are placeholders (app registered, empty models.py) so
TENANT_APPS is complete and migrations will pick them up correctly, but we'll
fill in their actual models feature-by-feature in later phases.

Update TENANT_APPS in settings to include all six apps. Confirm INSTALLED_APPS
computation still resolves correctly (no duplicate app registration between
SHARED_APPS and TENANT_APPS).

Do not run migrate_schemas --tenant yet — there's no tenant created to migrate
against. That happens in Prompt 6.
```

---



## Prompt 5 — JWT authentication

```
Wire up authentication using djangorestframework-simplejwt with the following
non-default behavior:

1. Access token: short-lived (15 min), returned in the response body, stored
   client-side in memory (frontend responsibility, not backend).
2. Refresh token: longer-lived (7 days), set as an httpOnly, Secure,
   SameSite=Strict cookie — NOT returned in the JSON response body.
3. Custom TokenObtainPairView subclass that sets the refresh token cookie on
   login response and only returns the access token in the body.
4. Custom TokenRefreshView subclass that reads the refresh token FROM the
   cookie (not the request body) and returns a new access token.
5. Logout endpoint that blacklists the current refresh token and clears the
   cookie. Add 'rest_framework_simplejwt.token_blacklist' to SHARED_APPS
   (token blacklist is identity-related, belongs in shared schema) and
   migrate it.
6. CSRF: since the refresh endpoint is cookie-based, ensure CSRF protection
   is active for that specific endpoint. Confirm normal JWT-authenticated
   API calls (using the Authorization header) remain CSRF-exempt as
   standard DRF/SimpleJWT behavior dictates.
7. Add a custom claim to the access token payload: school_id — but note this
   will be null/empty until SchoolMembership logic determines it; add a
   TODO comment for wiring this once multi-membership handling is decided
   in a later phase (a user may belong to multiple tenants).

Show me the four endpoints (login, refresh, logout, and confirm which view
handles token verification if any) and their URLs.
```

---



## Prompt 6 — Local dev tenant + docker setup

```
1. Create a Django management command `create_test_tenant` that, given a
   school name and subdomain, creates a Tenant + Domain record for local
   development testing (e.g., `python manage.py create_test_tenant
   "Test Academy" testacademy`).
2. Run migrate_schemas --tenant against this newly created tenant schema
   to confirm the tenant app tables (memberships_schoolmembership, plus
   empty academics/assessment/attendance/finance/communications apps) get
   created correctly in the isolated schema.
3. Create docker-compose.yml for local development with services: web
   (Django), db (postgres:16), redis. Match the existing pattern from the
   incel-hrm project — CapRover-compatible Dockerfile, environment variables
   sourced from .env, no hardcoded secrets.
4. Add a README.md section documenting: how to run migrate_schemas --shared,
   how to create a new tenant locally, how to run migrate_schemas --tenant,
   and how to hit the local subdomain (note: local subdomain testing requires
   either editing /etc/hosts or using a tool like nip.io — document whichever
   approach you set up).

Confirm the full loop works: create tenant → migrate tenant schema → the
tenant's schema has all six tenant apps' tables present (even if mostly empty
for now).
```

---



## Prompt 7 — CORS, rate limiting, and Sentry

```
1. Configure django-cors-headers to allow the Next.js frontend origin(s) —
   read allowed origins from an environment variable
   (CORS_ALLOWED_ORIGINS), don't hardcode.
2. Apply django-ratelimit (or DRF throttle classes — pick one and justify
   the choice) to the login and token refresh endpoints specifically, to
   protect against brute-force attempts. A reasonable starting limit:
   5 attempts per minute per IP — flag this as tunable, not final.
3. Wire up sentry-sdk in settings/production.py only (not local), reading
   SENTRY_DSN from environment, with Django + Celery integrations enabled.
4. Show me the final settings/base.py, settings/local.py, and
   settings/production.py in full so I can review before we move to
   building the first real feature module.
```

---



## After completing all prompts

You should have: a working multi-tenant Django project, one test tenant
provisioned locally, JWT auth with secure refresh-token handling, and a
docker-compose setup ready for CapRover deployment. Nothing feature-specific
(academics, assessment, finance) has real models yet — that's Phase 1 onward
per the PRD roadmap.

Before moving to Phase 1 (IAM/RBAC completion + academic structure), confirm:

- [ ] `migrate_schemas --shared` and `--tenant` both run cleanly
- [ ] A test tenant's schema is genuinely isolated (query in one schema
  ```
  doesn't leak into another — test manually with two test tenants)
  ```
- [ ] Login → refresh → logout cycle works end-to-end via Bruno or curl
- [ ] No secrets committed anywhere in the repo