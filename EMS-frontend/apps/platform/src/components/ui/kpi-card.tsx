import { cn } from "@/lib/cn";
import { Card, CardBody, type CardAccentTop } from "./card";

export type KpiCardProps = {
  label: string;
  value: string;
  delta?: string;
  accentTop?: CardAccentTop;
  className?: string;
};

export function KpiCard({
  label,
  value,
  delta,
  className,
}: KpiCardProps) {
  return (
    <Card className={className}>
      <CardBody className="space-y-1 py-4">
        <p className="text-sm font-medium text-ink/65">{label}</p>
        <p
          className="text-2xl font-bold tracking-tight md:text-[1.75rem]"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {value}
        </p>
        {delta ? (
          <p
            className="text-sm text-ink/60"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {delta}
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}
