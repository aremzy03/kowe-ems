import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
};

export function PageHeader({
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        "mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <h1
          className="text-[1.75rem] font-bold leading-tight tracking-tight md:text-[2rem]"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-[0.95rem] leading-relaxed text-ink/70">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  );
}
