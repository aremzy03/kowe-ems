"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import type { SchoolRole } from "@/lib/auth/token-store";
import { useAppSession } from "@/lib/auth/use-app-session";

const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

type RoleGuardProps = {
  allow: SchoolRole[];
  children: ReactNode;
};

/**
 * Client auth guard — role from AuthProvider / mock session.
 * Does not read API-host refresh_token. Does not select tenant schema.
 */
export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { role, accessToken, ready } = useAppSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!ready) return;

    const hasSession = Boolean(accessToken || (useMocks && role) || role);

    if (!hasSession || !role) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
      return;
    }

    if (!allow.includes(role)) {
      router.replace("/403");
    }
  }, [ready, role, accessToken, allow, router, pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-ink/70">
        Checking session…
      </div>
    );
  }

  if (!role || !allow.includes(role)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-ink/70">
        {!role ? "Redirecting to login…" : "Not allowed for this role…"}
      </div>
    );
  }

  return <>{children}</>;
}
