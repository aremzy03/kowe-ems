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
  success: "bg-wash-success text-ink",
  warning: "bg-wash-warning text-ink",
  danger: "bg-wash-danger text-ink",
  info: "bg-wash-info text-ink",
};

export function Badge({
  className,
  variant = "default",
  children,
  style,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-nb-sm)] border border-ink px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-[0.06em] shadow-nb-sm",
        variantClasses[variant],
        className,
      )}
      style={{ ...style, fontFamily: "var(--font-mono)" }}
      {...props}
    >
      {children}
    </span>
  );
}
