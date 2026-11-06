import { clearCsrfToken } from "@/lib/api/csrf";

/**
 * In-memory access token store (+ optional sessionStorage).
 * Never store the refresh token in JS — it is httpOnly on the API host.
 *
 * XSS note: sessionStorage persistence of the access JWT is convenient for
 * reload but readable by any XSS on the school origin. Prefer short-lived
 * access tokens; clear on logout.
 *
 * Platform sessions use separate keys (`apps/platform`).
 */

export type SchoolRole =
  | "admin"
  | "teacher"
  | "bursar"
  | "parent"
  | "platform_admin";

const ACCESS_KEY = "ems_school_access";
const ROLE_KEY = "ems_school_role";
const PRE_AUTH_KEY = "ems_school_pre_auth";

let memoryAccess: string | null = null;
let memoryRole: SchoolRole | null = null;
let memoryPreAuth: string | null = null;

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof sessionStorage !== "undefined";
}

export function getAccessToken(): string | null {
  if (memoryAccess) return memoryAccess;
  if (!canUseStorage()) return null;
  return sessionStorage.getItem(ACCESS_KEY);
}

export function setAccessToken(token: string | null): void {
  memoryAccess = token;
  if (!canUseStorage()) return;
  if (token) sessionStorage.setItem(ACCESS_KEY, token);
  else sessionStorage.removeItem(ACCESS_KEY);
}

export function getRole(): SchoolRole | null {
  if (memoryRole) return memoryRole;
  if (!canUseStorage()) return null;
  const raw = sessionStorage.getItem(ROLE_KEY);
  return (raw as SchoolRole | null) ?? null;
}

export function setRole(role: SchoolRole | null): void {
  memoryRole = role;
  if (!canUseStorage()) return;
  if (role) sessionStorage.setItem(ROLE_KEY, role);
  else sessionStorage.removeItem(ROLE_KEY);
}

export function getPreAuthToken(): string | null {
  if (memoryPreAuth) return memoryPreAuth;
  if (!canUseStorage()) return null;
  return sessionStorage.getItem(PRE_AUTH_KEY);
}

export function setPreAuthToken(token: string | null): void {
  memoryPreAuth = token;
  if (!canUseStorage()) return;
  if (token) sessionStorage.setItem(PRE_AUTH_KEY, token);
  else sessionStorage.removeItem(PRE_AUTH_KEY);
}

export function clearSchoolSession(): void {
  setAccessToken(null);
  setRole(null);
  setPreAuthToken(null);
  clearCsrfToken();
}

export type AuthTokens = {
  access: string;
  role?: SchoolRole;
};
