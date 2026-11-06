"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { academicsApi, type Session, type Term } from "@/lib/api/academics";
import { MOCK_SESSION_TERM } from "@/lib/mocks/staff-nav";
import { cn } from "@/lib/cn";

const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

type StaffTopbarProps = {
  onMenuClick?: () => void;
  className?: string;
};

/** Prefer the active term; fall back to first term under the active session. */
function liveTermLabel(sessions: Session[], terms: Term[]): string {
  const sessionById = new Map(sessions.map((s) => [s.id, s]));
  const activeTerm = terms.find((t) => t.is_active);
  if (activeTerm) {
    const sessionName =
      sessionById.get(activeTerm.session)?.name ?? "Session";
    return `${sessionName} · ${activeTerm.name}`;
  }
  const activeSession = sessions.find((s) => s.is_active);
  if (activeSession) {
    const termInSession = terms.find((t) => t.session === activeSession.id);
    if (termInSession) {
      return `${activeSession.name} · ${termInSession.name}`;
    }
    return activeSession.name;
  }
  return "No active term";
}

export function StaffTopbar({ onMenuClick, className }: StaffTopbarProps) {
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
    enabled: !useMocks,
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
    enabled: !useMocks,
  });

  const termLabel = useMemo(() => {
    if (useMocks) return MOCK_SESSION_TERM;
    if (sessions.isLoading || terms.isLoading) return "…";
    if (sessions.isError || terms.isError) return "Term unavailable";
    return liveTermLabel(sessions.data ?? [], terms.data ?? []);
  }, [
    sessions.data,
    sessions.isLoading,
    sessions.isError,
    terms.data,
    terms.isLoading,
    terms.isError,
  ]);

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
        aria-label="Current session and term"
      >
        {termLabel}
      </span>
    </header>
  );
}
