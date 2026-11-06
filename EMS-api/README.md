# EMS-api

## Phase 0 — local development (tenants + Docker)

Settings module: `config.settings.local` (also the `manage.py` default). Use the project `.venv` and `.env`. Postgres for this machine is typically the `ems-postgres` container on **host port 5433** (5432 was already in use). `docker-compose.yml` uses `${DB_PORT:-5433}` so it stays aligned with `.env`.

### Shared schema migrations

```bash
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.local
python manage.py migrate_schemas --shared
```

This applies public-schema apps (`platform_admin`, `accounts`, auth, JWT blacklist, etc.).

### Create a local tenant

```bash
python manage.py create_test_tenant "Test Academy" testacademy
```

That creates:

- a `Tenant` whose `schema_name` is derived from the subdomain (`testacademy`; hyphens become underscores)
- a primary `Domain` of `testacademy.localhost`

### Tenant schema migrations

```bash
python manage.py migrate_schemas --tenant
```

`create_test_tenant` also auto-creates the schema and runs tenant migrations on save (`TenantMixin.auto_create_schema`). Re-running `--tenant` is idempotent and confirms `memberships` (and other tenant apps) are applied. Placeholder apps with no models (`academics`, `assessment`, `attendance`, `finance`, `communications`) may add **no extra tables**; `memberships_schoolmembership` must exist.

### Single API host + tenant header (Phase 0.1)

The API is **one host**. django-tenants still uses per-school schemas; `HeaderTenantMiddleware` selects the schema from:

1. JWT claim `tenant_schema` (authenticated requests)
2. Header `X-Tenant-Slug` (pre-auth: login, signup, invite accept)
3. Otherwise 400 `Tenant identification required` — except `/api/auth/`, `/api/platform/`, and `/api/webhooks/` which stay on the public schema

Do **not** call `http://testacademy.localhost:8000/` to pick a school. Run the API on localhost (or `api.localhost`):

```bash
python manage.py runserver 127.0.0.1:8000
# or: python manage.py runserver api.localhost:8000
```

School UI stays on a frontend subdomain (`http://testacademy.localhost:3000`). Every school API call must send:

```http
X-Tenant-Slug: testacademy
```

The slug is the first label of the frontend hostname (`testacademy` from `testacademy.localhost`) and is looked up against `Domain` / `Tenant.schema_name`.

**Frontend `/etc/hosts` (SPA only, not the API):**

```text
127.0.0.1  testacademy.localhost
127.0.0.1  api.localhost
```

Invite emails use `TENANT_FRONTEND_ORIGIN_TEMPLATE` (local default `http://{slug}.localhost:3000`).

Paystack webhooks POST to the same API host: `POST /api/webhooks/paystack/` (no tenant header; tenant is the subaccount code in the payload).

### Docker Compose

Services: `web` (Django), `db` (`postgres:16`), `redis`. Env comes from `.env`; compose overrides `DB_HOST=db` and `REDIS_URL` for in-network access. `web` waits for the `db` healthcheck.

If `ems-postgres` is already bound to 5433, skip starting `db` or stop that container first:

```bash
docker compose up --build
# or, using existing host Postgres on 5433:
docker compose up --build web redis
```

CapRover deploys from the root `Dockerfile` (Python 3.12-slim, gunicorn on port 80, `config.settings.production`). `collectstatic` is not run at image build.

### WeasyPrint (report card PDFs)

Report cards use [WeasyPrint](https://weasyprint.org/). Pip alone is not enough — Pango (and related libs) must be on the system.

**Docker / CapRover:** the root `Dockerfile` installs the Debian packages WeasyPrint documents for wheels (`libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0`, plus `fonts-dejavu-core` and GDK Pixbuf). Rebuild the image after pulling those changes.

**Local (WSL / Debian / Ubuntu) inside the project venv:**

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
  libgdk-pixbuf-2.0-0 fonts-dejavu-core
source .venv/bin/activate
pip install -r requirements.txt   # includes weasyprint==68.1
```

Smoke-test: `python -c "from weasyprint import HTML; HTML(string='<h1>ok</h1>').write_pdf()"`

PDF endpoint: `GET /api/assessment/report-cards/?student=<uuid>&term=<uuid>` (downloadable attachment). Ranks/averages come from `TermResultSummary` — run class recompute first. Attendance is compute-on-read from daily marks; with no records the PDF shows “Attendance data not available” (not zeros).

---

## JWT refresh cookie (Prompt 5)

| Setting | Value |
|---|---|
| Cookie name | `refresh_token` |
| Flags | httpOnly, SameSite=`AUTH_REFRESH_COOKIE_SAMESITE` (default Strict) |
| Path | `/api/auth/` (sent only to login / refresh / logout) |
| Domain | Host-only on the **API host** unless `AUTH_COOKIE_DOMAIN` is set |
| Secure | `AUTH_COOKIE_SECURE` — **True in production**, **False in `local.py`** so `http://localhost` can set the cookie |

Access tokens are 15 minutes and returned in JSON only (and include `tenant_schema`). Refresh tokens are 7 days, cookie-only (not in the JSON body). Token rotation + blacklist is enabled on refresh; logout blacklists the current refresh token.

Production (`schoola.yourapp.com` → `api.yourapp.com`) is same-site: Strict host-only refresh cookies work. Set `CSRF_COOKIE_DOMAIN=.yourapp.com` so the SPA can read `csrftoken` and send `X-CSRFToken`. Local `testacademy.localhost:3000` → `localhost:8000` is **cross-site**; the refresh cookie will not be sent with SameSite=Strict.

Auth URLs: `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/logout/`, `/api/auth/verify/`.
Refresh and logout require a CSRF header (`X-CSRFToken`) matching Django’s `csrftoken` cookie (set on login). Bearer JWT API calls remain CSRF-exempt.

---

## CORS, auth throttles, and Sentry (Prompt 7)

**CORS:** `CORS_ALLOWED_ORIGINS` is a comma-separated env list; `CORS_ALLOWED_ORIGIN_REGEXES` covers school frontend subdomains (e.g. `^https://[\\w-]+\\.yourapp\\.com$`). Credentials are always allowed so the refresh cookie can be sent. `X-Tenant-Slug` is in `CORS_ALLOW_HEADERS`. Production hard-sets `CORS_ALLOW_ALL_ORIGINS=False`. Local defaults to `CORS_ALLOW_ALL_ORIGINS=True` (convenience); set it `False` in `.env` to use the explicit list / regexes. `CSRF_TRUSTED_ORIGINS` accepts Django wildcards (`https://*.yourapp.com`, `http://*.localhost:3000`).

**Throttles:** DRF `AuthEndpointThrottle` on `POST /api/auth/login/` and `POST /api/auth/refresh/` only — 5 requests per minute per IP (`AUTH_THROTTLE_RATE`). Tunable, not a final policy. Logout and verify are not throttled by this class.

**Sentry:** initialized in `config.settings.production` only, when `SENTRY_DSN` is set, with Django and Celery integrations. Not wired in `local.py`.
