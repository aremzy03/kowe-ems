# EMS Design System — "Paper Brutalism"

A **flat paper** operating surface with **neo-brutalism as punctuation**, not as chrome.
The interface should feel like writing in a well-made notebook: cream stock, ink lines, quiet columns — then a stamped button or a status chip when something must be acted on.

**From Codecademy / Gamut (layout & flatness):** cream field, thin ink rules, a left nav with a single active bar, a content column that leads with a large heading then one wide paper card. Generous whitespace. Almost no shadow on dashboards.

**From neo-brutalism (touches only):** hard offset shadows, thicker ink, press-into-the-page physics — reserved for primary buttons, badges, empty states, auth cards, and modals.

**Paper concept:** cream base instead of stark white; ink that is soft charcoal-plum, not pure black; Kalam only on signature lines, receipts, and empty-state asides — never chrome, forms, or data.

Colors stay. Intensity moved.

---

## 1. Color tokens

| Token | Value | Role |
|---|---|---|
| `--color-ink` | `#211F26` | Text, hairline rules, neo-brutalist shadows |
| `--color-paper` | `#FBF6EC` | Page and sidebar field — warm cream |
| `--color-paper-tint` | `#F3EBDA` | Active nav wash, nested well |
| `--color-paper-card` | `#FFFFFB` | Card surface — a shade lighter so the sheet sits on the desk |
| `--color-accent-1` | `#5B3DE8` | Primary CTA fill, focus ring |
| `--color-accent-2` | `#FF7A45` | Fee-due emphasis, secondary highlight |
| `--color-success` | `#1C9C7C` | Paid, present, approved |
| `--color-warning` | `#F5A623` | Pending, partial, awaiting review |
| `--color-danger` | `#E14B4B` | Overdue, absent, rejected |

- Color is categorical, never gradient.
- Status is never color alone — badge = color + label.
- Accent is for actions and state, not sidebar chrome.

## 2. Borders

| Token | Value | Use |
|---|---|---|
| `--border-hairline` | `1px solid var(--color-ink)` | Cards, sidebar, topbar, tables, inputs — default operating chrome |
| `--border-thin` | `1.5px solid var(--color-ink)` | Dense table header rules |
| `--border` | `2px solid var(--color-ink)` | Buttons, badges, auth inputs |
| `--border-thick` | `3px solid var(--color-ink)` | Auth cards, empty states, modals |

## 3. Shadows — earned, not default

Hard offset, **zero blur**. Most of the app has **no shadow**.

| Token | Value | Use |
|---|---|---|
| `--shadow-sm` | `2px 2px 0 0 var(--color-ink)` | Badges |
| `--shadow` | `4px 4px 0 0 var(--color-ink)` | Primary / secondary / inverted buttons |
| `--shadow-lg` | `7px 7px 0 0 var(--color-ink)` | Button hover, auth cards, empty states |
| `--shadow-xl` | `10px 10px 0 0 var(--color-ink)` | Modals |

Do **not** put offset shadows on sidebar, topbar, dashboard cards, tables, or KPI tiles.

## 4. Radius

| Token | Value |
|---|---|
| `--radius-sm` | `4px` — badges, chips, inputs, cards |
| `--radius` | `6px` — buttons |
| `--radius-lg` | `8px` — auth cards, modals |

Slightly cut-paper, never pills, never 0.

## 5. Typography

| Role | Font | Use |
|---|---|---|
| Heading | Space Grotesk (600/700) | Page titles, card titles, nav labels |
| Body | Inter (400/500) | UI copy, table cells, labels — generous line-height |
| Mono | JetBrains Mono (400/700) | Admission numbers, ₦, linking codes, timestamps |
| Accent | Kalam (400/600) | Signature lines, empty-state asides only |

Page titles in the **content column** (not a second H1 in the topbar). Scale is product-tight: title ~1.75–2rem, not a marketing display.

## 6. Interaction

| Surface | Hover / press |
|---|---|
| Chrome, nav, cards, inputs | Background wash only. No lift. |
| `.nb-interactive` (buttons, auth role picks) | Hover `translate(-2px, -2px)` + shadow grows; press into the page, shadow none |
| Focus-visible | `outline: 3px solid var(--color-accent-1); outline-offset: 3px` |

## 7. Layout (Operate)

Codecademy-like topology:

1. **Left sidebar** (~248px) on the same cream as the page. Hairline right rule. Line icons + labels. Active item: 3px ink bar on the left + `--color-paper-tint` wash. No boxed nav buttons.
2. **Quiet top strip** — menu (mobile), session/term mono pill. No duplicate page title.
3. **Content column** — max ~72rem, generous padding. Page heading, then a wide paper card (or a quiet KPI row + one card).
4. **Parent** — top wordmark + text tabs (underline/wash, not boxed); bottom tabs on small screens, same language.

Nested cards are wrong. A card contains lists, tables, and rows — it does not contain more cards.

## 8. Intensity

**Flat paper (default):** staff dashboards, tables, mark entry, attendance, fees, settings, parent portal chrome.

**Neo-brutalist (touches):** primary CTAs, badges, empty states, login / 2FA / signup / link-student, modals.

## 9. Accessibility

- Body text ≥ 4.5:1 on paper / paper-card.
- `--color-warning` is fill + ink text, never text-on-cream.
- Focus outline sits outside any hard shadow.
- Status is color + label.

## 10. Brand assets (Kowe)

Source of truth: `kowe_brand_assets/kowe-logo-kit/` (see `KOWE-logo-guidelines.md`). Runtime copies live in each app’s `public/` (`favicon*` / icons at root; lockups under `public/brand/`).

| Surface | Asset | Component |
|---|---|---|
| Auth / onboarding / portal home | `kowe-horizontal.svg` (≥96 px wide) | `KoweLockup` |
| Staff sidebar, parent/platform chrome | `kowe-symbol.svg` (≥24 px); `kowe-symbol-small.svg` under 24 px | `KoweMark` |
| Browser / PWA | `web/` favicons + `site.webmanifest` | Next `metadata.icons` |

- Clear space: ½ tile height around every lockup.
- Never retype the wordmark in a UI font; Operate chrome is **symbol + school/platform label only**.
- Don’t place full-colour logo on Coral; don’t stretch or recolour outside the palette.

---

## Tailwind (`src/app/globals.css`)

Tokens live in `@theme`. Keep the root `globals.css` copy in sync.

## Fonts (`src/app/layout.tsx`)

Space Grotesk, Inter, JetBrains Mono, Kalam as `--font-heading`, `--font-body`, `--font-mono`, `--font-accent` on `<body>`.
