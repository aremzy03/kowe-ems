import { PLATFORM_API_URL } from "@/lib/api/config";
import { csrfHeaders, captureCsrfFromResponse } from "@/lib/api/csrf";
import {
  clearPlatformSession,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/token-store";

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
  /** Platform client always omits X-Tenant-Slug; scope kept for shared patterns. */
  scope?: "platform";
  /** Override Bearer token (e.g. pre_auth for 2FA enroll). */
  accessToken?: string | null;
  skipRefresh?: boolean;
  signal?: AbortSignal;
  headers?: Record<string, string>;
};

let refreshPromise: Promise<string | null> | null = null;

function extractDetail(data: unknown): string | undefined {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return undefined;
}

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${PLATFORM_API_URL}/api/auth/refresh/`, {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...(await csrfHeaders()),
        },
        body: "{}",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        clearPlatformSession();
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
      clearPlatformSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

/**
 * Platform apiFetch — default (and only) scope is platform.
 * Never attaches X-Tenant-Slug.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    auth = false,
    accessToken,
    skipRefresh = false,
    signal,
    headers: extra,
  } = options;

  const urlPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${PLATFORM_API_URL}${urlPath}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...extra,
  };

  if (body !== undefined) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }

  if (
    method !== "GET" &&
    method !== "HEAD" &&
    (urlPath === "/api/auth/refresh/" || urlPath === "/api/auth/logout/")
  ) {
    Object.assign(headers, await csrfHeaders());
  }

  const bearer =
    accessToken !== undefined ? accessToken : auth ? getAccessToken() : null;
  if (bearer) {
    headers.Authorization = `Bearer ${bearer}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    credentials: "include",
    body:
      body === undefined
        ? undefined
        : typeof body === "string"
          ? body
          : JSON.stringify(body),
    signal,
  });

  const contentType = res.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json")
    ? await res.json().catch(() => ({}))
    : await res.text().catch(() => "");

  if (res.ok) {
    if (urlPath.startsWith("/api/auth/")) {
      captureCsrfFromResponse(data);
    }
    return data as T;
  }

  const detail = extractDetail(data);

  if (res.status === 401 && detail === "Invalid tenant claim in token.") {
    clearPlatformSession();
    throw new ApiRequestError({ status: res.status, data, detail });
  }

  if (
    res.status === 401 &&
    auth &&
    !skipRefresh &&
    accessToken === undefined
  ) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, { ...options, skipRefresh: true });
    }
    clearPlatformSession();
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new ApiRequestError({ status: 401, data, detail });
  }

  throw new ApiRequestError({ status: res.status, data, detail });
}
