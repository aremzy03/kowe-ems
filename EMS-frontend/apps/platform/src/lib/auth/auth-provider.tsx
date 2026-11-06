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
import {
  displayNameFromMe,
  me as fetchMe,
  refresh as refreshAuth,
  type MeResponse,
} from "@/lib/api/auth";
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
  displayName: string | null;
  setSession: (access: string, role: string, profile?: MeResponse | null) => void;
  clearSession: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccess] = useState<string | null>(null);
  const [role, setRoleState] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const applyMe = useCallback((profile: MeResponse) => {
    setDisplayName(displayNameFromMe(profile));
    if (profile.role) {
      setRole(profile.role);
      setRoleState(profile.role);
    }
  }, []);

  const loadMe = useCallback(async () => {
    try {
      const profile = await fetchMe();
      applyMe(profile);
    } catch {
      // Keep token/role; header falls back to "Platform".
    }
  }, [applyMe]);

  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      let token = getAccessToken();
      const existingRole = getRole();
      if (!token) {
        const refreshed = await refreshAuth();
        if (cancelled) return;
        if (refreshed?.access) {
          setAccessToken(refreshed.access);
          token = refreshed.access;
        }
      }
      if (cancelled) return;
      if (token) {
        setAccess(token);
        setRoleState(existingRole ?? getRole());
        await loadMe();
      }
      if (!cancelled) setReady(true);
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [loadMe]);

  const setSession = useCallback(
    (access: string, nextRole: string, profile?: MeResponse | null) => {
      setAccessToken(access);
      setRole(nextRole);
      setAccess(access);
      setRoleState(nextRole);
      if (profile) applyMe(profile);
      else void loadMe();
    },
    [applyMe, loadMe],
  );

  const clearSession = useCallback(() => {
    clearPlatformSession();
    setAccess(null);
    setRoleState(null);
    setDisplayName(null);
  }, []);

  const value = useMemo(
    () => ({ accessToken, role, ready, displayName, setSession, clearSession }),
    [accessToken, role, ready, displayName, setSession, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
