"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { refresh as refreshAuth } from "@/lib/api/auth";
import {
  clearPlatformSession,
  getAccessToken,
  getRole,
  setAccessToken,
  setRole,
} from "@/lib/auth/token-store";

type AuthContextValue = {
  accessToken: string | null;
  role: string | null;
  ready: boolean;
  setSession: (access: string, role: string) => void;
  clearSession: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccess] = useState<string | null>(null);
  const [role, setRoleState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      const existing = getAccessToken();
      const existingRole = getRole();
      if (existing) {
        if (!cancelled) {
          setAccess(existing);
          setRoleState(existingRole);
          setReady(true);
        }
        return;
      }
      const refreshed = await refreshAuth();
      if (cancelled) return;
      if (refreshed?.access) {
        setAccessToken(refreshed.access);
        setAccess(refreshed.access);
        setRoleState(getRole());
      }
      setReady(true);
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const setSession = useCallback((access: string, nextRole: string) => {
    setAccessToken(access);
    setRole(nextRole);
    setAccess(access);
    setRoleState(nextRole);
  }, []);

  const clearSession = useCallback(() => {
    clearPlatformSession();
    setAccess(null);
    setRoleState(null);
  }, []);

  const value = useMemo(
    () => ({ accessToken, role, ready, setSession, clearSession }),
    [accessToken, role, ready, setSession, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
