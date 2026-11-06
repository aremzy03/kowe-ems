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
  clearSchoolSession,
  getAccessToken,
  getRole,
  setAccessToken,
  setRole,
  type SchoolRole,
} from "@/lib/auth/token-store";

type AuthContextValue = {
  accessToken: string | null;
  role: SchoolRole | null;
  ready: boolean;
  setSession: (access: string, role: SchoolRole) => void;
  clearSession: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccess] = useState<string | null>(null);
  const [role, setRoleState] = useState<SchoolRole | null>(null);
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

      // Attempt cookie refresh when SameSite allows (prod / same-site local).
      // Local *.localhost → localhost:8000 often fails — documented caveat.
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

  const setSession = useCallback((access: string, nextRole: SchoolRole) => {
    setAccessToken(access);
    setRole(nextRole);
    setAccess(access);
    setRoleState(nextRole);
  }, []);

  const clearSession = useCallback(() => {
    clearSchoolSession();
    setAccess(null);
    setRoleState(null);
  }, []);

  const value = useMemo(
    () => ({
      accessToken,
      role,
      ready,
      setSession,
      clearSession,
    }),
    [accessToken, role, ready, setSession, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
