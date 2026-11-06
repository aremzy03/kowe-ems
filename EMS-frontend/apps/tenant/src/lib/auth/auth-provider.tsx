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
  schoolNameFromMe,
  type MeResponse,
} from "@/lib/api/auth";
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
  displayName: string | null;
  schoolName: string | null;
  setSession: (
    access: string,
    role: SchoolRole,
    profile?: MeResponse | null,
  ) => void;
  clearSession: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function isSchoolRole(value: string | null | undefined): value is SchoolRole {
  return (
    value === "admin" ||
    value === "teacher" ||
    value === "bursar" ||
    value === "parent" ||
    value === "platform_admin"
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccess] = useState<string | null>(null);
  const [role, setRoleState] = useState<SchoolRole | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [schoolName, setSchoolName] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const applyMe = useCallback((profile: MeResponse) => {
    setDisplayName(displayNameFromMe(profile));
    setSchoolName(schoolNameFromMe(profile));
    if (isSchoolRole(profile.role)) {
      setRole(profile.role);
      setRoleState(profile.role);
    }
  }, []);

  const loadMe = useCallback(async () => {
    try {
      const profile = await fetchMe();
      applyMe(profile);
    } catch {
      // Token/role still apply; greetings fall back to the role label.
    }
  }, [applyMe]);

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      let token = getAccessToken();
      const existingRole = getRole();
      if (!token) {
        // Attempt cookie refresh when SameSite allows (prod / same-site local).
        // Local *.localhost → localhost:8000 often fails — documented caveat.
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
    (access: string, nextRole: SchoolRole, profile?: MeResponse | null) => {
      setAccessToken(access);
      setRole(nextRole);
      setAccess(access);
      setRoleState(nextRole);
      if (profile) {
        applyMe(profile);
      } else {
        void loadMe();
      }
    },
    [applyMe, loadMe],
  );

  const clearSession = useCallback(() => {
    clearSchoolSession();
    setAccess(null);
    setRoleState(null);
    setDisplayName(null);
    setSchoolName(null);
  }, []);

  const value = useMemo(
    () => ({
      accessToken,
      role,
      ready,
      displayName,
      schoolName,
      setSession,
      clearSession,
    }),
    [
      accessToken,
      role,
      ready,
      displayName,
      schoolName,
      setSession,
      clearSession,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
