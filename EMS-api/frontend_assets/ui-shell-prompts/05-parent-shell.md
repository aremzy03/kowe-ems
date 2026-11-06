# 05 — Parent App Shell

**Goal:** Parent chrome (mobile-friendly + desktop usable).

**Acceptance:** Parent routes use bottom tabs on small screens; top bar on desktop; child switcher slot ready.

### Agent prompt

```
Implement EMS parent portal shell for (parent) route group.

Mobile (default):
- Top bar: EMS wordmark, school name, profile button
- Main scroll area bg #f7f9f1
- Bottom tab bar: white, 3px top border — tabs Home, Results, Fees, More
- Active tab: bg #ffde4d, text black, 2px border

Desktop (≥1024):
- Optional left compact nav OR keep top tabs under header — pick one and stay consistent
- Wider content max-width container

Export ParentShell and wire app/(parent)/layout.tsx.
Include a ChildSwitcher placeholder component (horizontal cards) that reads mock children from lib/mocks/parent.ts — selected child fill #00f0ff.

Logout from More/profile clears mock session.
```
