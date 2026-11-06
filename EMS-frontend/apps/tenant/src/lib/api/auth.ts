import { apiFetch } from "@/lib/api/client";
import { PLATFORM_ORIGIN } from "@/lib/api/config";
import { setCsrfToken } from "@/lib/api/csrf";
import {
  clearSchoolSession,
  setAccessToken,
  setPreAuthToken,
  setRole,
  type SchoolRole,
} from "@/lib/auth/token-store";

export type MeResponse = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: SchoolRole | null;
  membership_id: string | null;
  is_active: boolean;
  tenant_schema: string;
  tenant_slug: string | null;
  school_name: string | null;
};

export type LoginResponse = {
  access?: string;
  role?: SchoolRole;
  requires_2fa?: boolean;
  pre_auth_token?: string;
  enrollment_required?: boolean;
  csrfToken?: string;
  me?: MeResponse;
};

export function displayNameFromMe(me: MeResponse): string {
  const full = `${me.first_name ?? ""} ${me.last_name ?? ""}`.trim();
  return full || me.email || "User";
}

export function schoolNameFromMe(me: MeResponse): string {
  return (me.school_name ?? "").trim() || "School";
}

/** In-app homes for school roles. Platform UI lives in apps/platform (absolute origin). */
export type RoleHome = "/admin" | "/teacher" | "/bursar" | "/parent";

export const ROLE_HOME: Record<Exclude<SchoolRole, "platform_admin">, RoleHome> =
  {
    admin: "/admin",
    teacher: "/teacher",
    bursar: "/bursar",
    parent: "/parent",
  };

/**
 * After school-app login/2FA: school roles stay in-app; platform_admin goes to apps/platform.
 * Prefer this over ROLE_HOME[role] so platform_admin never hits removed /platform routes.
 */
export function navigateAfterAuth(
  role: SchoolRole,
  router: { push: (href: string) => void },
  next?: string | null,
): void {
  if (role === "platform_admin") {
    if (typeof window !== "undefined") {
      window.location.assign(PLATFORM_ORIGIN);
    }
    return;
  }
  const dest =
    next && next.startsWith("/") && !next.startsWith("//")
      ? next
      : ROLE_HOME[role];
  router.push(dest);
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: { email, password },
    auth: false,
    scope: "tenant",
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
    scope: "tenant",
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
    scope: "tenant",
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
    scope: "tenant",
  });
}

export async function me(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/api/auth/me/", {
    auth: true,
    scope: "tenant",
  });
}

export async function refresh(): Promise<{ access: string } | null> {
  try {
    return await apiFetch<{ access: string }>("/api/auth/refresh/", {
      method: "POST",
      body: {},
      auth: false,
      scope: "tenant",
      skipRefresh: true,
    });
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/auth/logout/", {
      method: "POST",
      body: {},
      auth: true,
      scope: "tenant",
      skipRefresh: true,
    });
  } finally {
    clearSchoolSession();
  }
}

export type AcceptInvitePayload = {
  token: string;
  password: string;
  first_name: string;
  last_name: string;
};

export async function acceptInvite(payload: AcceptInvitePayload) {
  return apiFetch("/api/memberships/invites/accept/", {
    method: "POST",
    body: payload,
    auth: false,
    scope: "tenant",
  });
}

export type ParentSignupPayload = {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
};

export async function parentSignup(payload: ParentSignupPayload) {
  return apiFetch("/api/memberships/parents/signup/", {
    method: "POST",
    body: payload,
    auth: false,
    scope: "tenant",
  });
}

/** Persist successful school session after login / 2FA. */
export function applyAuthSuccess(data: LoginResponse): SchoolRole | null {
  if (data.csrfToken) setCsrfToken(data.csrfToken);
  if (data.access) setAccessToken(data.access);
  if (data.role) setRole(data.role);
  setPreAuthToken(null);
  return data.role ?? null;
}

export function applyPreAuthChallenge(data: LoginResponse): void {
  if (data.csrfToken) setCsrfToken(data.csrfToken);
  if (data.pre_auth_token) setPreAuthToken(data.pre_auth_token);
  if (data.role) setRole(data.role);
  setAccessToken(null);
}
