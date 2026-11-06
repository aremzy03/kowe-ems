import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Card, CardBody } from "./card";

export type EmptyStateProps = {
  headline: string;
  body: string;
  /** Kalam aside. Pass `null` to hide; omit for a contextual default. */
  aside?: string | null;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  className?: string;
};

function defaultAside(headline: string): string {
  const h = headline.toLowerCase();
  if (h.includes("tenant") || h.includes("school")) {
    return "Provision from CLI for now — the list will fill in.";
  }
  if (h.includes("webhook")) {
    return "Quiet channel — events show up when schools pay.";
  }
  if (h.includes("match") || h.includes("filter") || h.includes("result")) {
    return "Widen the filter, or wait for the next event.";
  }
  return "Quiet for now — check back after the next step.";
}

export function EmptyState({
  headline,
  body,
  aside,
  primaryAction,
  secondaryAction,
  className,
}: EmptyStateProps) {
  const asideText = aside === undefined ? defaultAside(headline) : aside;

  return (
    <Card raised className={cn("mx-auto max-w-lg", className)}>
      <CardBody className="space-y-4 p-8 text-center">
        <h2
          className="text-2xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {headline}
        </h2>
        <p className="text-ink/80">{body}</p>
        {asideText ? (
          <p
            className="text-sm text-accent-2"
            style={{ fontFamily: "var(--font-accent)" }}
          >
            {asideText}
          </p>
        ) : null}
        {(primaryAction || secondaryAction) && (
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            {primaryAction}
            {secondaryAction}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
