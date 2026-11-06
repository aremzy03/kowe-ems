import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export function Table({
  className,
  ...props
}: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card">
      <table className={cn("w-full border-collapse text-left text-sm", className)} {...props} />
    </div>
  );
}

export function THead({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn("bg-paper-tint [&_th]:border-b [&_th]:border-ink/20", className)}
      {...props}
    />
  );
}

export function TBody({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("[&_tr:hover]:bg-ink/[0.03]", className)} {...props} />;
}

export function TR({
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("border-b border-ink/15 last:border-b-0", className)}
      {...props}
    />
  );
}

export function TH({
  className,
  ...props
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn("px-3 py-2 font-semibold text-ink", className)}
      style={{ fontFamily: "var(--font-heading)" }}
      {...props}
    />
  );
}

export function TD({
  className,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-3 py-2 text-ink", className)} {...props} />;
}
