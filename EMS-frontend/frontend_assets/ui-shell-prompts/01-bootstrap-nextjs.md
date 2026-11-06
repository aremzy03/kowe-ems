# 01 — Bootstrap Next.js App

**Goal:** Create the Next.js 15 App Router project and install the design tokens.

**Acceptance:** `npm run dev` works; root layout loads Space Grotesk + JetBrains Mono; `globals.css` contains EMS tokens from `frontend_assets/index.css`.

### Agent prompt

```
Create a Next.js 15 TypeScript App Router project for EMS (or configure the existing frontend repo if one already exists).

Requirements:
1. Tailwind CSS v4. Port design tokens from the handoff file `frontend_assets/index.css` in the EMS-api repo into `app/globals.css` (or `src/app/globals.css`) — keep the :root variables, @theme inline mapping, and base layer.
2. Root layout patterned after `frontend_assets/layout.tsx`: next/font Google Space_Grotesk + JetBrains_Mono, CSS variables on <body>, metadata title "EMS".
3. ESLint + path alias `@/*`.
4. `.env.local.example` with NEXT_PUBLIC_API_URL and NEXT_PUBLIC_TENANT_HOST placeholders (unused until API phase).
5. Homepage is a temporary stub listing role entry links (Admin / Teacher / Bursar / Parent / Platform) — neo-brutalist cards, not a marketing landing.

Do not add API clients, auth libraries, or TanStack Query yet.
Do not redesign the color palette.
Commit-ready structure only; keep the diff focused.
```
