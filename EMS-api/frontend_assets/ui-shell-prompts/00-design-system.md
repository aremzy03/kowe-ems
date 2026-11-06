# 00 — Design System (Agent Context)

> Keep this file attached or paste once at the start of the UI-shell workstream. Source: `frontend_assets/index.css` + `layout.tsx`.

### Agent prompt

```
You are building the EMS (Educational Management System) frontend for Nigerian K-12 schools.

Visual system — neo-brutalism on our brand tokens (do NOT invent a generic yellow/black palette):

Colors (light):
- background #f7f9f1, foreground #000000, card #ffffff
- primary #0e4bcd, secondary #3537a7
- muted #f1f5f9, muted-foreground #475569
- accent #00f0ff, destructive #ff4d4d
- ring / primary CTA fill #ffde4d
- sidebar #dce2ca

Structure:
- border 3px solid #000 (2px inside tables)
- radius 4px everywhere
- hard offset shadows only: 5px 4px 0 #000 (zero blur). No soft/Material shadows.
- focus ring: 3px #ffde4d outside the shadow

Typography:
- Space Grotesk for UI + headings
- JetBrains Mono for admission numbers, ₦ amounts, codes, timestamps

Component rules:
- Primary CTA: bg #ffde4d, text black, 3px border, hard shadow; hover lift; active press into shadow
- Never white text on yellow or cyan
- State is never color-only (badge = color + label)
- Dial UP on auth/empty/CTAs; MEDIUM on dashboards; DOWN on dense tables and money forms
- No gradients, no fully-rounded pills, no glassmorphism

Locale: Nigeria, English, currency ₦, classes like JSS 1A, session 2025/2026.

Acknowledge these rules and wait for the next numbered prompt before coding.
```
