/**
 * CSRF for refresh/logout (platform app).
 *
 * Prefer JSON `csrfToken` from login or GET /api/auth/csrf/.
 * Do not rely on document.cookie — platform.localhost → localhost:8000 is
 * cross-site and the API host cookie is not readable from the SPA.
 */

import { PLATFORM_API_URL } from "@/lib/api/config";

const CSRF_KEY = "ems_platform_csrf";

let memoryCsrf: string | null = null;
let fetchPromise: Promise<string | null> | null = null;

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof sessionStorage !== "undefined";
}

function cookieCsrf(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function getCsrfToken(): string | null {
  if (memoryCsrf) return memoryCsrf;
  if (canUseStorage()) {
    const stored = sessionStorage.getItem(CSRF_KEY);
    if (stored) {
      memoryCsrf = stored;
      return stored;
    }
  }
  return cookieCsrf();
}

export function setCsrfToken(token: string | null): void {
  memoryCsrf = token;
  if (!canUseStorage()) return;
  if (token) sessionStorage.setItem(CSRF_KEY, token);
  else sessionStorage.removeItem(CSRF_KEY);
}

export function clearCsrfToken(): void {
  setCsrfToken(null);
}

function pickCsrfFromBody(data: unknown): string | null {
  if (
    typeof data === "object" &&
    data !== null &&
    "csrfToken" in data &&
    typeof (data as { csrfToken: unknown }).csrfToken === "string"
  ) {
    return (data as { csrfToken: string }).csrfToken;
  }
  return null;
}

export function captureCsrfFromResponse(data: unknown): void {
  const token = pickCsrfFromBody(data);
  if (token) setCsrfToken(token);
}

/** Never sends X-Tenant-Slug. */
export async function ensureCsrfToken(): Promise<string | null> {
  const existing = getCsrfToken();
  if (existing) return existing;

  if (typeof window === "undefined") return null;

  if (fetchPromise) return fetchPromise;

  fetchPromise = (async () => {
    try {
      const res = await fetch(`${PLATFORM_API_URL}/api/auth/csrf/`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      const data = await res.json().catch(() => ({}));
      const token = pickCsrfFromBody(data);
      if (token) setCsrfToken(token);
      return token ?? cookieCsrf();
    } catch {
      return cookieCsrf();
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export async function csrfHeaders(): Promise<Record<string, string>> {
  const token = await ensureCsrfToken();
  return token ? { "X-CSRFToken": token } : {};
}
