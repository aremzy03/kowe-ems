import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export type CardAccentTop = "accent-1" | "accent-2" | "warning" | "danger";

export type CardProps = HTMLAttributes<HTMLDivElement> & {
  /** Optional 1px ink-adjacent tint — not a loud accent bar */
  accentTop?: CardAccentTop;
  /** Neo-brutalist lift — auth, empty states only */
  raised?: boolean;
  /** Interior coral margin. One working sheet per view. */
  ledger?: boolean;
  children: ReactNode;
};

const accentTopClasses: Record<CardAccentTop, string> = {
  "accent-1": "border-t-accent-1",
  "accent-2": "border-t-accent-2",
  warning: "border-t-warning",
  danger: "border-t-danger",
};

export function Card({
  className,
  accentTop,
  raised,
  ledger,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "relative rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card",
        raised && "rounded-[var(--radius-nb-lg)] border-[3px] shadow-nb-lg",
        accentTop && cn("border-t", accentTopClasses[accentTop]),
        ledger && "pl-12 sm:pl-16",
        className,
      )}
      {...props}
    >
      {ledger ? (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-8 w-[1.5px] bg-accent-2/45 sm:left-12"
        />
      ) : null}
      {children}
    </div>
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "border-b-[1.5px] border-dashed border-rule px-5 py-4",
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({
  className,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-lg font-bold", className)}
      style={{ fontFamily: "var(--font-heading)" }}
      {...props}
    />
  );
}

export function CardBody({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}
