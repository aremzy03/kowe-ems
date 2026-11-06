# EMS Platform Admin

Workspace app `@ems/platform` — public-schema operator UI. Never sends `X-Tenant-Slug`.

| Service | URL |
|---|---|
| This app | `http://platform.localhost:3001` |
| API | `http://localhost:8000` |

## Env

See `apps/platform/.env.local.example`. From monorepo root:

```bash
npm run dev:platform
```

## Bound APIs

- `POST /api/auth/login/` (`scope: 'platform'`)
- `GET /api/platform/revenue/`
- Refresh / logout omit tenant header

Tenants / webhooks pages are empty-state only until list APIs exist.

## Cookie caveat

Same as tenant app: `platform.localhost` → `localhost:8000` is cross-site; Strict refresh cookie may not send. See `docs/INTEGRATION.md`.
