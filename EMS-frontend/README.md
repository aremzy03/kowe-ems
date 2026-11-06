# EMS Frontends (monorepo)

npm workspaces with two Next.js apps wired to EMS-api:

| App | Path | Local URL |
|---|---|---|
| Tenant (school) | `apps/tenant` | `http://testacademy.localhost:3000` |
| Platform admin | `apps/platform` | `http://platform.localhost:3001` |
| API (single host) | — | `http://localhost:8000` |

Add to `/etc/hosts` (or rely on `*.localhost` resolution):

```
127.0.0.1 testacademy.localhost
127.0.0.1 platform.localhost
```

Do **not** use `testacademy.localhost:8000` as the API base. Tenant selection is `X-Tenant-Slug`, not Host on the API.

## Env

**Tenant** — copy `apps/tenant/.env.local.example` → `apps/tenant/.env.local`:

```
NEXT_PUBLIC_TENANT_API_URL=http://localhost:8000
NEXT_PUBLIC_PLATFORM_API_URL=http://localhost:8000
NEXT_PUBLIC_ROOT_DOMAIN=localhost
NEXT_PUBLIC_PLATFORM_HOST=platform.localhost
NEXT_PUBLIC_PLATFORM_ORIGIN=http://platform.localhost:3001
# NEXT_PUBLIC_USE_MOCKS=true
```

**Platform** — copy `apps/platform/.env.local.example` → `apps/platform/.env.local`:

```
NEXT_PUBLIC_PLATFORM_API_URL=http://localhost:8000
NEXT_PUBLIC_ROOT_DOMAIN=localhost
```

## Run

```bash
npm install          # from repo root
npm run dev:tenant   # http://testacademy.localhost:3000
npm run dev:platform # http://platform.localhost:3001
```

`npm run dev` starts the tenant app only.

Dev ping: `http://testacademy.localhost:3000/dev/api-ping` (shows `X-Tenant-Slug` in Network).

## Auth + tenant

See `docs/API_MAPPING.md` and `docs/INTEGRATION.md`.

School calls always send `X-Tenant-Slug` (first hostname label). Platform app omits it.
