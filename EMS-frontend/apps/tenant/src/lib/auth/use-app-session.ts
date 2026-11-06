"use client";

import { useCallback, useMemo } from "react";
import { useAuth } from "@/lib/auth/auth-provider";
import { logout as apiLogout } from "@/lib/api/auth";
import type { SchoolRole } from "@/lib/auth/token-store";
import {
  clearMockSession,
  useMockSession,
} from "@/lib/mocks/session-client";

const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

const ROLE_DISPLAY: Record<SchoolRole, string> = {
  admin: "Admin",
  teacher: "Teacher",
  bursar: "Bursar",
  parent: "Parent",
  platform_admin: "Platform admin",
};

/**
 * Live mode has no person name yet: login returns only access+role, JWT claims
 * are user_id / tenant_schema / role / school_id (no first_name), and there is
 * no /api/auth/me. Fallback is a single title-cased role label so greetings
 * read "Welcome, Teacher" without the old "bursar" raw slug. Pages that still
 * prefix the role in titles (e.g. "Bursar · …") should drop that prefix when
 * they rewrite — do not invent a second name string here.
 */
function liveDisplayName(role: SchoolRole | null): string {
  if (!role) return "User";
  return ROLE_DISPLAY[role] ?? role.replace(/_/g, " ");
}

/**
 * Unified display session: real AuthProvider, or mock cookie when USE_MOCKS.
 * MockSessionProvider must always be mounted (see Providers).
 */
export function useAppSession() {
  const auth = useAuth();
  const mock = useMockSession();

  const role: SchoolRole | null = useMocks
    ? (mock.role as SchoolRole | null) ?? auth.role
    : auth.role;

  const displayName = useMocks
    ? (mock.user?.name ?? "User")
    : liveDisplayName(role);

  const schoolName = useMocks
    ? (mock.user?.schoolName ?? "School")
    : "School";

  const logout = useCallback(async () => {
    if (useMocks) {
      clearMockSession();
    }
    try {
      await apiLogout();
    } catch {
      auth.clearSession();
    }
    window.location.href = "/login";
  }, [auth]);

  return useMemo(
    () => ({
      role,
      displayName,
      schoolName,
      accessToken: auth.accessToken,
      ready: auth.ready || useMocks,
      logout,
    }),
    [role, displayName, schoolName, auth.accessToken, auth.ready, logout],
  );
}
