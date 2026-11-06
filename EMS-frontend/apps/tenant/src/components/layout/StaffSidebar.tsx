"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge, Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  STAFF_NAV,
  isStaffRole,
  type StaffNavItem,
} from "@/lib/mocks/staff-nav";
import { useAppSession } from "@/lib/auth/use-app-session";
import { KoweMark } from "./KoweMark";
import { StaffNavIcon } from "./StaffNavIcon";

function isNavActive(pathname: string, href: string, items: StaffNavItem[]) {
  if (pathname === href) return true;
  if (href === items[0]?.href) return false;
  const longerChildMatches = items.some(
    (item) =>
      item.href !== href &&
      item.href.length > href.length &&
      item.href.startsWith(`${href}/`) &&
      (pathname === item.href || pathname.startsWith(`${item.href}/`)),
  );
  if (longerChildMatches) return false;
  return pathname.startsWith(`${href}/`);
}

const ROLE_BADGE_LABEL: Record<string, string> = {
  admin: "Admin",
  teacher: "Teacher",
  bursar: "Bursar",
};

type StaffSidebarProps = {
  onNavigate?: () => void;
  className?: string;
};

export function StaffSidebar({ onNavigate, className }: StaffSidebarProps) {
  const pathname = usePathname();
  const { role, displayName, schoolName, logout } = useAppSession();

  if (!isStaffRole(role)) {
    return null;
  }

  const items = STAFF_NAV[role];

  function handleLogout() {
    void logout();
  }

  return (
    <aside
      className={cn(
        "flex h-full w-[248px] flex-col border-r border-ink/20 bg-paper",
        className,
      )}
    >
      <div className="px-5 py-6">
        <div className="flex items-center gap-3">
          <KoweMark size={32} />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-ink/80">{schoolName}</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4" aria-label="Staff">
        {items.map((item) => {
          const active = isNavActive(pathname, item.href, items);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "relative flex items-center gap-3 rounded-[var(--radius-nb-sm)] px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-paper-tint font-semibold text-ink"
                  : "font-medium text-ink/70 hover:bg-paper-tint/60 hover:text-ink",
              )}
              style={{ fontFamily: "var(--font-heading)" }}
              aria-current={active ? "page" : undefined}
            >
              {active ? (
                <span
                  className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-sm bg-ink"
                  aria-hidden
                />
              ) : null}
              <StaffNavIcon href={item.href} className="shrink-0 opacity-80" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-ink/15 px-4 py-4">
        <p
          className="truncate text-sm font-semibold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {displayName}
        </p>
        <div className="mt-2">
          <Badge variant="default">{ROLE_BADGE_LABEL[role] ?? role}</Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="mt-3 w-full"
          onClick={handleLogout}
        >
          Log out
        </Button>
      </div>
    </aside>
  );
}
