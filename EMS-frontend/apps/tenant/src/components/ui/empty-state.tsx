import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Card, CardBody } from "./card";

export type EmptyStateProps = {
  headline: string;
  body: string;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  className?: string;
};

export function EmptyState({
  headline,
  body,
  primaryAction,
  secondaryAction,
  className,
}: EmptyStateProps) {
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
        <p
          className="text-sm text-accent-2"
          style={{ fontFamily: "var(--font-accent)" }}
        >
          Nothing here yet — try another path.
        </p>
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
