"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { logout } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/auth-provider";
import { KoweMark } from "./KoweMark";

const PLATFORM_NAV = [
  { href: "/", label: "Revenue", match: (p: string) => p === "/" },
  {
    href: "/tenants",
    label: "Tenants",
    match: (p: string) => p.startsWith("/tenants"),
  },
  {
    href: "/webhooks",
    label: "Webhooks",
    match: (p: string) => p.startsWith("/webhooks"),
  },
] as const;

export function PlatformShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { accessToken, role, ready } = useAuth();

  useEffect(() => {
    if (!ready) return;
    if (!accessToken || role !== "platform_admin") {
      window.location.assign("/login");
    }
  }, [ready, accessToken, role]);

  if (!ready || !accessToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-ink/70">
        Checking session…
      </div>
    );
  }

  async function handleLogout() {
    await logout();
    window.location.assign("/login");
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3 md:px-8">
          <KoweMark size={28} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink/80">Platform</p>
          </div>
          <nav className="flex flex-wrap gap-1" aria-label="Platform">
            {PLATFORM_NAV.map((item) => {
              const active = item.match(pathname);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-[var(--radius-nb-sm)] px-3 py-1.5 text-sm",
                    active
                      ? "bg-paper-tint font-semibold text-ink"
                      : "font-medium text-ink/65 hover:bg-paper-tint/70 hover:text-ink",
                  )}
                  style={{ fontFamily: "var(--font-heading)" }}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <Button variant="ghost" size="sm" onClick={() => void handleLogout()}>
            Log out
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 md:px-8">{children}</main>
    </div>
  );
}
