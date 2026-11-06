import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type PencilAsideProps = HTMLAttributes<HTMLParagraphElement> & {
  children: string;
};

/** One italic Kalam line per view, for a fact already in the loaded data. */
export function PencilAside({ className, children, ...props }: PencilAsideProps) {
  return (
    <p
      className={cn(
        "border-l-[3px] border-accent-2 bg-paper-card px-4 py-3 text-base italic leading-relaxed text-ink",
        className,
      )}
      style={{ fontFamily: "var(--font-accent)" }}
      {...props}
    >
      {children}
    </p>
  );
}
