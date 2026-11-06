"use client";

import { MOCK_SESSION_TERM } from "@/lib/mocks/staff-nav";
import { cn } from "@/lib/cn";

type StaffTopbarProps = {
  onMenuClick?: () => void;
  className?: string;
};

export function StaffTopbar({ onMenuClick, className }: StaffTopbarProps) {
  return (
    <header
      className={cn(
        "flex items-center gap-3 border-b border-ink/15 bg-paper px-4 py-3 md:px-8",
        className,
      )}
    >
      <button
        type="button"
        onClick={onMenuClick}
        className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-nb-sm)] border border-ink/30 bg-paper-card lg:hidden"
        aria-label="Open navigation"
      >
        <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden>
          <path
            d="M1 1h16M1 7h16M1 13h16"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </button>

      <div className="min-w-0 flex-1" />

      <span
        className="shrink-0 rounded-[var(--radius-nb-sm)] border border-ink/25 bg-paper-card px-2.5 py-1 text-xs font-medium text-ink/75 md:text-sm"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {MOCK_SESSION_TERM}
      </span>
    </header>
  );
}
