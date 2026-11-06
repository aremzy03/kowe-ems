import { apiFetch } from "@/lib/api/client";
import { setCsrfToken } from "@/lib/api/csrf";
import {
  clearPlatformSession,
  setAccessToken,
  setPreAuthToken,
  setRole,
} from "@/lib/auth/token-store";

export type MeResponse = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string | null;
  membership_id: string | null;
  is_active: boolean;
  tenant_schema: string;
  tenant_slug: string | null;
  school_name: string | null;
};

export type LoginResponse = {
  access?: string;
  role?: string;
  requires_2fa?: boolean;
  pre_auth_token?: string;
  enrollment_required?: boolean;
  csrfToken?: string;
  me?: MeResponse;
};

export const PLATFORM_ADMIN_ROLE = "platform_admin";

export function isPlatformAdminRole(
  role: string | null | undefined,
): role is typeof PLATFORM_ADMIN_ROLE {
  return role === PLATFORM_ADMIN_ROLE;
}

export function displayNameFromMe(me: MeResponse): string {
  const full = `${me.first_name ?? ""} ${me.last_name ?? ""}`.trim();
  return full || me.email || "Operator";
}

export async function login(email: string, password: string) {
  return apiFetch<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: { email, password },
    auth: false,
    scope: "platform",
  });
}

export async function verify2fa(
  pre_auth_token: string,
  totp_code: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/2fa/verify/", {
    method: "POST",
    body: { pre_auth_token, totp_code },
    auth: false,
    scope: "platform",
  });
}

export async function enroll2fa(preAuthToken: string): Promise<{
  secret: string;
  config_url: string;
  qr_code: string;
}> {
  return apiFetch("/api/auth/2fa/enroll/", {
    method: "POST",
    body: {},
    auth: true,
    accessToken: preAuthToken,
    skipRefresh: true,
    scope: "platform",
  });
}

export async function confirmEnroll2fa(
  preAuthToken: string,
  totp_code: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/2fa/enroll/confirm/", {
    method: "POST",
    body: { totp_code, issue_tokens: true },
    auth: true,
    accessToken: preAuthToken,
    skipRefresh: true,
    scope: "platform",
  });
}

export async function me(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/api/auth/me/", {
    auth: true,
    scope: "platform",
  });
}

export async function logout() {
  try {
    await apiFetch("/api/auth/logout/", {
      method: "POST",
      body: {},
      auth: true,
      scope: "platform",
      skipRefresh: true,
    });
  } finally {
    clearPlatformSession();
  }
}

export async function refresh() {
  try {
    return await apiFetch<{ access: string }>("/api/auth/refresh/", {
      method: "POST",
      body: {},
      auth: false,
      scope: "platform",
      skipRefresh: true,
    });
  } catch {
    return null;
  }
}

export type RevenueOverview = {
  period: { from?: string; to?: string };
  totals: {
    gross_amount: string;
    commission_amount: string;
    net_to_school: string;
    transaction_count: number;
  };
  by_school: Array<{
    tenant_id?: string;
    schema_name?: string;
    school_name?: string;
    name?: string;
    gross_amount: string;
    commission_amount: string;
    net_to_school: string;
    transaction_count?: number;
  }>;
};

export async function fetchRevenue() {
  return apiFetch<RevenueOverview>("/api/platform/revenue/", {
    auth: true,
    scope: "platform",
  });
}

/** Persist a full platform session after login / 2FA. */
export function applyAuthSuccess(data: LoginResponse): string | null {
  if (data.csrfToken) setCsrfToken(data.csrfToken);
  if (data.access) setAccessToken(data.access);
  if (data.role) setRole(data.role);
  setPreAuthToken(null);
  return data.role ?? null;
}

/** Store the pending 2FA challenge; do not keep a full access token. */
export function applyPreAuthChallenge(data: LoginResponse): void {
  if (data.csrfToken) setCsrfToken(data.csrfToken);
  if (data.pre_auth_token) setPreAuthToken(data.pre_auth_token);
  if (data.role) setRole(data.role);
  setAccessToken(null);
}

