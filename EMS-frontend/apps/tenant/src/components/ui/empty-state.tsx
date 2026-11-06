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
  if (h.includes("select") || h.includes("choose")) {
    return "Pick one above, then come back.";
  }
  if (h.includes("assign")) {
    return "Ask admin if this looks wrong.";
  }
  if (h.includes("invoice")) {
    return "Fresh term, blank ledger — that's fine.";
  }
  if (h.includes("fee")) {
    return "Set the structure first; invoices follow.";
  }
  if (h.includes("link") || h.includes("student")) {
    return "One code from school unlocks the rest.";
  }
  if (h.includes("access") || h.includes("denied") || h.includes("forbidden")) {
    return "Wrong door — try another path.";
  }
  if (h.includes("term") || h.includes("session")) {
    return "Sessions and terms come before the rest.";
  }
  if (h.includes("match") || h.includes("filter") || h.includes("result")) {
    return "Widen the filter, or wait for the next publish.";
  }
  if (h.includes("staff") || h.includes("api")) {
    return "Invites first — the directory fills after accept.";
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
