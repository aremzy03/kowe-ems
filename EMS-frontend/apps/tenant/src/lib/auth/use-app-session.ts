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
    : role
      ? role.replace("_", " ")
      : "User";

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
