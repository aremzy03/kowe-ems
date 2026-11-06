"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { useAppSession } from "@/lib/auth/use-app-session";
import { ChildSwitcher } from "./ChildSwitcher";
import { EmsMark } from "./EmsMark";

const PARENT_TABS = [
  { href: "/parent", label: "Home", match: (p: string) => p === "/parent" },
  {
    href: "/parent/students",
    label: "Students",
    match: (p: string) => p.startsWith("/parent/students"),
  },
  {
    href: "/parent/results",
    label: "Results",
    match: (p: string) => p.startsWith("/parent/results"),
  },
  {
    href: "/parent/attendance",
    label: "Attendance",
    match: (p: string) => p.startsWith("/parent/attendance"),
  },
  {
    href: "/parent/fees",
    label: "Fees",
    match: (p: string) => p.startsWith("/parent/fees"),
  },
  {
    href: "/parent/more",
    label: "More",
    match: (p: string) => p.startsWith("/parent/more"),
  },
] as const;

type ParentShellProps = {
  children: ReactNode;
};

export function ParentShell({ children }: ParentShellProps) {
  const pathname = usePathname();
  const { displayName, schoolName, logout } = useAppSession();

  function handleLogout() {
    void logout();
  }

  return (
    <div className="flex min-h-screen flex-col bg-paper text-ink">
      <header className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3 md:px-6">
          <EmsMark size={28} />
          <div className="min-w-0 flex-1">
            <p
              className="text-lg font-bold leading-none"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              EMS
            </p>
            <p className="mt-0.5 truncate text-sm text-ink/60">{schoolName}</p>
          </div>
          <Link
            href="/parent/more"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-ink/25 bg-paper-card text-sm font-bold"
            style={{ fontFamily: "var(--font-heading)" }}
            aria-label="Profile and more"
          >
            {(displayName ?? "P").charAt(0)}
          </Link>
        </div>

        <nav
          className="mx-auto hidden max-w-5xl items-center gap-1 px-4 pb-2 md:px-6 lg:flex"
          aria-label="Parent"
        >
          {PARENT_TABS.map((tab) => {
            const active = tab.match(pathname);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "rounded-[var(--radius-nb-sm)] px-3 py-2 text-sm",
                  active
                    ? "bg-paper-tint font-semibold text-ink"
                    : "font-medium text-ink/65 hover:bg-paper-tint/70 hover:text-ink",
                )}
                style={{ fontFamily: "var(--font-heading)" }}
                aria-current={active ? "page" : undefined}
              >
                {tab.label}
              </Link>
            );
          })}
          <button
            type="button"
            onClick={handleLogout}
            className="ml-auto px-3 py-2 text-sm font-medium text-ink/65 hover:text-ink"
            style={{ fontFamily: "var(--font-heading)" }}
          >
            Log out
          </button>
        </nav>
      </header>

      <div className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 md:px-6 md:py-8">
        <ChildSwitcher className="mb-6" />
        {children}
      </div>

      <nav
        className="sticky bottom-0 z-30 border-t border-ink/15 bg-paper lg:hidden"
        aria-label="Parent mobile"
      >
        <div className="mx-auto flex max-w-5xl gap-1 overflow-x-auto p-2">
          {PARENT_TABS.map((tab) => {
            const active = tab.match(pathname);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "flex min-w-[4.5rem] flex-1 flex-col items-center justify-center rounded-[var(--radius-nb-sm)] px-1 py-2 text-[11px]",
                  active
                    ? "bg-paper-tint font-semibold text-ink"
                    : "font-medium text-ink/60",
                )}
                style={{ fontFamily: "var(--font-heading)" }}
                aria-current={active ? "page" : undefined}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
