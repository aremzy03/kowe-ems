/**
 * Platform session keys — must not collide with school EMS-frontend keys
 * (ems_school_*).
 */

import { clearCsrfToken } from "@/lib/api/csrf";

const ACCESS_KEY = "ems_platform_access";
const ROLE_KEY = "ems_platform_role";
const PRE_AUTH_KEY = "ems_platform_pre_auth";

let memoryAccess: string | null = null;
let memoryRole: string | null = null;
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

export function getRole(): string | null {
  if (memoryRole) return memoryRole;
  if (!canUseStorage()) return null;
  return sessionStorage.getItem(ROLE_KEY);
}

export function setRole(role: string | null): void {
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

export function clearPlatformSession(): void {
  setAccessToken(null);
  setRole(null);
  setPreAuthToken(null);
  clearCsrfToken();
}
