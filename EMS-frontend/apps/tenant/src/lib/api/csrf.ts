/**
 * CSRF for refresh/logout.
 *
 * Prefer the JSON `csrfToken` from login / 2FA / GET /api/auth/csrf/.
 * Do not rely on `document.cookie` for `csrftoken` when the SPA is on a
 * different host than the API (e.g. *.localhost → localhost:8000) — that
 * cookie is host-only on the API origin and is not readable cross-site.
 *
 * Cookie read is kept only as a same-site production fallback.
 */

import { PLATFORM_API_URL, TENANT_API_URL } from "@/lib/api/config";
import { getTenantSlug } from "@/lib/api/tenant";

export type CsrfScope = "tenant" | "platform";

const CSRF_KEY = "ems_school_csrf";

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

/** Persist csrfToken from login / 2FA / refresh JSON when present. */
export function captureCsrfFromResponse(data: unknown): void {
  const token = pickCsrfFromBody(data);
  if (token) setCsrfToken(token);
}

/**
 * Ensure we have a CSRF token for X-CSRFToken.
 * Fetches GET /api/auth/csrf/ when nothing is stored / readable.
 */
export async function ensureCsrfToken(
  scope: CsrfScope = "tenant",
): Promise<string | null> {
  const existing = getCsrfToken();
  if (existing) return existing;

  if (typeof window === "undefined") return null;

  if (fetchPromise) return fetchPromise;

  fetchPromise = (async () => {
    try {
      const base = scope === "platform" ? PLATFORM_API_URL : TENANT_API_URL;
      const headers: Record<string, string> = { Accept: "application/json" };

      if (scope === "tenant") {
        const slug = getTenantSlug(window.location.hostname);
        if (slug) headers["X-Tenant-Slug"] = slug;
      }

      const res = await fetch(`${base}/api/auth/csrf/`, {
        method: "GET",
        credentials: "include",
        headers,
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

export async function csrfHeaders(
  scope: CsrfScope = "tenant",
): Promise<Record<string, string>> {
  const token = await ensureCsrfToken(scope);
  return token ? { "X-CSRFToken": token } : {};
}
