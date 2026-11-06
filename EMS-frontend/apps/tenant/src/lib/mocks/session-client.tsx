"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  EMS_MOCK_ROLE_COOKIE,
  getMockUser,
  isMockRole,
  ROLE_HOME,
  type MockRole,
  type MockUser,
} from "./session";

function readRoleCookie(): MockRole | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${EMS_MOCK_ROLE_COOKIE}=`));
  if (!match) return null;
  const value = decodeURIComponent(match.split("=").slice(1).join("="));
  return isMockRole(value) ? value : null;
}

function subscribeToCookie(onStoreChange: () => void) {
  const onFocus = () => onStoreChange();
  window.addEventListener("focus", onFocus);
  window.addEventListener("ems-mock-session", onStoreChange);
  return () => {
    window.removeEventListener("focus", onFocus);
    window.removeEventListener("ems-mock-session", onStoreChange);
  };
}

function notifySessionChange() {
  window.dispatchEvent(new Event("ems-mock-session"));
}

export function setMockSession(role: MockRole) {
  const maxAge = 60 * 60 * 24 * 7;
  document.cookie = `${EMS_MOCK_ROLE_COOKIE}=${encodeURIComponent(role)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
  notifySessionChange();
}

export function clearMockSession() {
  document.cookie = `${EMS_MOCK_ROLE_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
  notifySessionChange();
}

const PENDING_2FA_KEY = "ems_pending_2fa_role";

export function setPending2faRole(role: MockRole) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(PENDING_2FA_KEY, role);
}

export function getPending2faRole(): MockRole | null {
  if (typeof window === "undefined") return null;
  const value = sessionStorage.getItem(PENDING_2FA_KEY);
  return isMockRole(value) ? value : null;
}

export function clearPending2faRole() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(PENDING_2FA_KEY);
}

/** Roles that must complete 2FA before a full mock session is set.
 * Off for now to match API ``REQUIRE_ADMIN_2FA=False``. */
export function roleRequires2fa(_role: MockRole): boolean {
  return false;
}

export function loginAsRole(role: MockRole) {
  setMockSession(role);
  window.location.href = ROLE_HOME[role];
}

/**
 * Start a mock login. 2FA challenge is off while roleRequires2fa is false.
 */
export function beginMockLogin(role: MockRole) {
  if (roleRequires2fa(role)) {
    setPending2faRole(role);
    window.location.href = `/2fa/verify?role=${encodeURIComponent(role)}`;
    return;
  }
  loginAsRole(role);
}

export function completeMock2fa(role?: MockRole | null) {
  const pending = role ?? getPending2faRole();
  if (!pending || !roleRequires2fa(pending)) {
    window.location.href = "/login";
    return;
  }
  clearPending2faRole();
  loginAsRole(pending);
}

type SessionContextValue = {
  role: MockRole | null;
  user: MockUser | null;
  setRole: (role: MockRole) => void;
  clear: () => void;
  loginAs: (role: MockRole) => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function MockSessionProvider({ children }: { children: ReactNode }) {
  const role = useSyncExternalStore(
    subscribeToCookie,
    readRoleCookie,
    () => null,
  );

  const setRole = useCallback((next: MockRole) => {
    setMockSession(next);
  }, []);

  const clear = useCallback(() => {
    clearMockSession();
  }, []);

  const loginAs = useCallback((next: MockRole) => {
    loginAsRole(next);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      role,
      user: role ? getMockUser(role) : null,
      setRole,
      clear,
      loginAs,
    }),
    [role, setRole, clear, loginAs],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useMockSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useMockSession must be used within MockSessionProvider");
  }
  return ctx;
}
