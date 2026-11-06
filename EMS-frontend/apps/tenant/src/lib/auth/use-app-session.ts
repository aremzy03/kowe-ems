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

function liveDisplayName(role: SchoolRole | null): string {
  if (!role) return "User";
  return ROLE_DISPLAY[role] ?? role.replace(/_/g, " ");
}

/**
 * Unified display session: real AuthProvider, or mock cookie when USE_MOCKS.
 * MockSessionProvider must always be mounted (see Providers).
 *
 * Live mode loads person + school from GET /api/auth/me/ (AuthProvider).
 * Until that lands, greetings fall back to a single title-cased role label.
 */
export function useAppSession() {
  const auth = useAuth();
  const mock = useMockSession();

  const role: SchoolRole | null = useMocks
    ? (mock.role as SchoolRole | null) ?? auth.role
    : auth.role;

  const displayName = useMocks
    ? (mock.user?.name ?? "User")
    : (auth.displayName ?? liveDisplayName(role));

  const schoolName = useMocks
    ? (mock.user?.schoolName ?? "School")
    : (auth.schoolName ?? "School");

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
