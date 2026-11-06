import { cn } from "@/lib/cn";
import { Card, CardBody, type CardAccentTop } from "./card";

export type KpiTone = "ink" | "coral" | "green";

export type KpiCardProps = {
  label: string;
  value: string;
  delta?: string;
  /** Numeral color. Ink unless the figure is outstanding, overdue, collected, present, or paid. */
  tone?: KpiTone;
  /** 0–100 from the API. Draws one hatch bar. The percentage text stays ink. */
  rate?: number;
  rateTone?: "coral" | "green";
  /** Real trend values. A dotted stroke renders only when at least two points exist. */
  series?: number[];
  accentTop?: CardAccentTop;
  className?: string;
};

const valueToneClass: Record<KpiTone, string> = {
  ink: "text-ink",
  coral: "text-accent-2-ink",
  green: "text-success-ink",
};

function RateBar({
  value,
  tone,
}: {
  value: number;
  tone: "coral" | "green";
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const hue = tone === "coral" ? "var(--color-accent-2)" : "var(--color-success)";

  return (
    <div className="mt-3 h-2 w-full border border-ink bg-kraft" aria-hidden>
      <div
        className="h-full"
        style={{
          width: `${clamped}%`,
          backgroundImage: `repeating-linear-gradient(45deg, ${hue} 0, ${hue} 1.5px, transparent 0, transparent 4px)`,
        }}
      />
    </div>
  );
}

function PencilSeries({ values }: { values: number[] }) {
  const width = 160;
  const height = 32;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * width;
    const y = height - 4 - ((value - min) / span) * (height - 8);
    return [x, y] as const;
  });
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point[0].toFixed(1)},${point[1].toFixed(1)}`)
    .join(" ");
  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="mt-2 h-8 w-full text-ink"
      aria-hidden
    >
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="1 3"
        strokeLinecap="round"
      />
      <circle
        cx={last[0]}
        cy={last[1]}
        r="3"
        fill="var(--color-accent-2)"
        stroke="var(--color-ink)"
        strokeWidth="1"
      />
    </svg>
  );
}

export function KpiCard({
  label,
  value,
  delta,
  tone = "ink",
  rate,
  rateTone = "green",
  series,
  className,
}: KpiCardProps) {
  const trend = series && series.length >= 2 ? series : null;
  const rateValue = typeof rate === "number" && Number.isFinite(rate) ? rate : null;

  return (
    <Card className={className}>
      <CardBody className="space-y-1 py-4">
        <p
          className="font-mono text-[11px] font-medium uppercase tracking-[0.06em] text-ink/75"
          style={{ fontFamily: "var(--font-mono)" }}
        >
          {label}
        </p>
        <p
          className={cn(
            "text-2xl font-bold tracking-tight tabular-nums md:text-[1.75rem]",
            valueToneClass[tone],
          )}
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {value}
        </p>
        {delta ? (
          <p
            className="text-sm text-ink/75"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {delta}
          </p>
        ) : null}
        {rateValue != null ? <RateBar value={rateValue} tone={rateTone} /> : null}
        {trend ? <PencilSeries values={trend} /> : null}
      </CardBody>
    </Card>
  );
}
