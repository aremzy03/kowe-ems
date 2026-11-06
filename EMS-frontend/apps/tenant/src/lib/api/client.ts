import {
  EMS_TENANT_SLUG_HEADER,
  PLATFORM_API_URL,
  TENANT_API_URL,
} from "@/lib/api/config";
import { csrfHeaders, captureCsrfFromResponse } from "@/lib/api/csrf";
import { getTenantSlug } from "@/lib/api/tenant";
import {
  clearSchoolSession,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/token-store";

export type ApiScope = "tenant" | "platform";

export type ApiError = {
  status: number;
  data: unknown;
  detail?: string;
};

export class ApiRequestError extends Error {
  status: number;
  data: unknown;
  detail?: string;

  constructor(error: ApiError) {
    const detail =
      typeof error.data === "object" &&
      error.data !== null &&
      "detail" in error.data &&
      typeof (error.data as { detail: unknown }).detail === "string"
        ? (error.data as { detail: string }).detail
        : error.detail;
    super(detail ?? `API error ${error.status}`);
    this.name = "ApiRequestError";
    this.status = error.status;
    this.data = error.data;
    this.detail = detail;
  }
}

export type ApiFetchOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  scope?: ApiScope;
  /** Override Bearer token (e.g. pre_auth for 2FA enroll). */
  accessToken?: string | null;
  headers?: Record<string, string>;
  /** Skip 401 refresh retry (used by refresh itself). */
  skipRefresh?: boolean;
  signal?: AbortSignal;
};

type RefreshState = {
  promise: Promise<string | null> | null;
};

const refreshState: RefreshState = { promise: null };

function extractDetail(data: unknown): string | undefined {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return undefined;
}

async function resolveTenantSlug(): Promise<string> {
  if (typeof window !== "undefined") {
    const slug = getTenantSlug(window.location.hostname);
    if (!slug) {
      throw new ApiRequestError({
        status: 0,
        data: {
          detail: `Tenant identification required: open the school UI on {slug}.${process.env.NEXT_PUBLIC_ROOT_DOMAIN ?? "localhost"}`,
        },
        detail: "Tenant identification required",
      });
    }
    return slug;
  }

  try {
    const { headers } = await import("next/headers");
    const h = await headers();
    const fromMw = h.get(EMS_TENANT_SLUG_HEADER);
    if (fromMw) return fromMw;
    const host = h.get("host") ?? "";
    const slug = getTenantSlug(host);
    if (slug) return slug;
  } catch {
    // Outside Next request context
  }

  throw new ApiRequestError({
    status: 0,
    data: { detail: "Tenant identification required" },
    detail: "Tenant identification required",
  });
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const next = window.location.pathname + window.location.search;
  const url = new URL("/login", window.location.origin);
  if (next && next !== "/login") url.searchParams.set("next", next);
  window.location.assign(url.toString());
}

async function refreshAccessToken(scope: ApiScope): Promise<string | null> {
  if (refreshState.promise) return refreshState.promise;

  refreshState.promise = (async () => {
    try {
      const base = scope === "platform" ? PLATFORM_API_URL : TENANT_API_URL;
      const headers: Record<string, string> = {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(await csrfHeaders(scope)),
      };

      if (scope === "tenant") {
        headers["X-Tenant-Slug"] = await resolveTenantSlug();
      }

      const res = await fetch(`${base}/api/auth/refresh/`, {
        method: "POST",
        credentials: "include",
        headers,
        body: "{}",
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        clearSchoolSession();
        return null;
      }
      captureCsrfFromResponse(data);
      const access =
        typeof data === "object" &&
        data !== null &&
        "access" in data &&
        typeof (data as { access: unknown }).access === "string"
          ? (data as { access: string }).access
          : null;
      if (access) setAccessToken(access);
      return access;
    } catch {
      clearSchoolSession();
      return null;
    } finally {
      refreshState.promise = null;
    }
  })();

  return refreshState.promise;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    auth = false,
    scope = "tenant",
    accessToken,
    headers: extraHeaders,
    skipRefresh = false,
    signal,
  } = options;

  const base = scope === "platform" ? PLATFORM_API_URL : TENANT_API_URL;
  const urlPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${base}${urlPath}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...extraHeaders,
  };

  if (scope === "tenant") {
    headers["X-Tenant-Slug"] = await resolveTenantSlug();
  }

  const needsCredentials =
    urlPath.startsWith("/api/auth/") ||
    method !== "GET" ||
    auth;

  if (body !== undefined) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }

  if (
    method !== "GET" &&
    method !== "HEAD" &&
    (urlPath === "/api/auth/refresh/" || urlPath === "/api/auth/logout/")
  ) {
    Object.assign(headers, await csrfHeaders(scope));
  }

  const bearer =
    accessToken !== undefined ? accessToken : auth ? getAccessToken() : null;
  if (bearer) {
    headers.Authorization = `Bearer ${bearer}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    credentials: needsCredentials ? "include" : "same-origin",
    body:
      body === undefined
        ? undefined
        : typeof body === "string"
          ? body
          : JSON.stringify(body),
    signal,
  });

  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const data = isJson
    ? await res.json().catch(() => ({}))
    : await res.arrayBuffer().catch(() => null);

  if (res.ok) {
    if (urlPath.startsWith("/api/auth/")) {
      captureCsrfFromResponse(data);
    }
    return data as T;
  }

  const detail = extractDetail(data);

  if (
    res.status === 400 &&
    (detail === "Tenant identification required" ||
      detail === "Unknown tenant.")
  ) {
    throw new ApiRequestError({ status: res.status, data, detail });
  }

  if (res.status === 401 && detail === "Invalid tenant claim in token.") {
    clearSchoolSession();
    throw new ApiRequestError({ status: res.status, data, detail });
  }

  if (res.status === 401 && auth && !skipRefresh && scope === "tenant") {
    const refreshed = await refreshAccessToken(scope);
    if (refreshed) {
      return apiFetch<T>(path, {
        ...options,
        accessToken: refreshed,
        skipRefresh: true,
      });
    }
    clearSchoolSession();
    redirectToLogin();
    throw new ApiRequestError({ status: 401, data, detail });
  }

  throw new ApiRequestError({ status: res.status, data, detail });
}
