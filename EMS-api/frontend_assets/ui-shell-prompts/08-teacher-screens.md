# 08 — Teacher Screens (Mock Data)

**Goal:** Teacher workflows UI — mark entry and attendance must feel fast (dial DOWN).

**Acceptance:** Mark entry table editable in React state; attendance toggles work locally; broadsheet renders mock grid.

### Agent prompt

```
Implement Teacher pages under app/(staff)/teacher with lib/mocks/teacher.ts.

Pages:
1. /teacher — Home: greeting, assignment cards (class+subject), form-teacher cards, pending chips
2. /teacher/marks — Mark entry: component select (1st CA/2nd CA/Exam), dense score table, sticky footer with counts, Save draft / Submit (toast mock). Persist edits in component state; optional localStorage key for offline demo.
3. /teacher/components — weight table with live total 100% validation UI
4. /teacher/broadsheet — wide mock grid student × subject, position column, Recompute + Download buttons (no-op/toast)
5. /teacher/attendance — register: Present/Late/Absent square toggles with labels+color; Save register
6. /teacher/remarks — student list + remark textareas + report card preview panel (static mock layout)

Intensity: DOWN on marks/attendance/broadsheet. Use mono for scores and admission numbers.
```
