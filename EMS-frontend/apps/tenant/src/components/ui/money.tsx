import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { formatNaira } from "@/lib/format-money";

export type MoneyProps = HTMLAttributes<HTMLSpanElement> & {
  amount: number;
};

/** All ₦ amounts use JetBrains Mono for trustworthy finance UI. */
export function Money({ amount, className, ...props }: MoneyProps) {
  return (
    <span
      className={cn("tabular-nums", className)}
      style={{ fontFamily: "var(--font-mono)" }}
      {...props}
    >
      {formatNaira(amount)}
    </span>
  );
}
