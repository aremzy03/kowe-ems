import { cn } from "@/lib/cn";

export type PencilBar = {
  label: string;
  /** 0–100. Days with no marks stay at 0. */
  value: number;
  marked?: number;
};

export type PencilBarsProps = {
  points: PencilBar[];
  className?: string;
};

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri"] as const;

function weekdayIndex(iso: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  const day = date.getDay();
  if (day === 0 || day === 6) return null;
  return day;
}

/** Present + late, grouped Mon–Fri. Returns null until two weekdays have marks. */
export function weekdayAttendanceRates(
  rows: { date?: string; status?: string }[],
): PencilBar[] | null {
  const buckets = WEEKDAY_LABELS.map(() => ({ attended: 0, marked: 0 }));
  for (const row of rows) {
    if (!row.date) continue;
    const index = weekdayIndex(row.date);
    if (index == null) continue;
    const status = (row.status ?? "").toLowerCase();
    if (!status) continue;
    const bucket = buckets[index - 1];
    bucket.marked += 1;
    if (status === "present" || status === "late") bucket.attended += 1;
  }
  const markedDays = buckets.filter((bucket) => bucket.marked > 0).length;
  if (markedDays < 2) return null;
  return WEEKDAY_LABELS.map((label, index) => {
    const bucket = buckets[index];
    return {
      label,
      marked: bucket.marked,
      value:
        bucket.marked === 0
          ? 0
          : Math.round((bucket.attended / bucket.marked) * 100),
    };
  });
}

/** Flat hatch chart. Peak bar uses coral. */
export function PencilBars({ points, className }: PencilBarsProps) {
  const peak = Math.max(...points.map((point) => point.value), 0);

  return (
    <div className={cn("flex h-40 items-end gap-2", className)}>
      {points.map((point) => {
        const isPeak = peak > 0 && point.value === peak;
        const height = point.marked === 0 ? 0 : Math.max(point.value, 4);
        return (
          <div
            key={point.label}
            className="flex h-full min-w-0 flex-1 flex-col items-center"
          >
            <span
              className="mb-1 font-mono text-[11px] font-bold tabular-nums tracking-[0.04em] text-ink"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {point.marked === 0 ? "—" : `${point.value}%`}
            </span>
            <div className="flex w-full flex-1 items-end">
              <div
                className={cn(
                  "w-full border border-ink bg-kraft",
                  isPeak && "border-2 border-accent-2",
                )}
                style={{
                  height: `${height}%`,
                  backgroundImage: isPeak
                    ? "repeating-linear-gradient(45deg, var(--color-accent-2) 0, var(--color-accent-2) 1.5px, transparent 0, transparent 4px)"
                    : "repeating-linear-gradient(45deg, var(--color-ink) 0, var(--color-ink) 1px, transparent 0, transparent 4px)",
                }}
              />
            </div>
            <span
              className="mt-2 font-mono text-[11px] font-bold uppercase tracking-[0.06em] text-ink"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {point.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
