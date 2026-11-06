import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
  /** Required label — status is always color + text */
  children: string;
};

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-paper-card text-ink",
  success: "bg-success text-paper-card",
  warning: "bg-warning text-ink",
  danger: "bg-danger text-paper-card",
  info: "bg-accent-1 text-paper-card",
};

export function Badge({
  className,
  variant = "default",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-nb-sm)] border border-ink px-2 py-0.5 text-xs font-semibold shadow-nb-sm",
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
