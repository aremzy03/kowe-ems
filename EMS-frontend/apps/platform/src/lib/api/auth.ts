import { apiFetch } from "@/lib/api/client";
import { setCsrfToken } from "@/lib/api/csrf";
import {
  clearPlatformSession,
  setAccessToken,
  setRole,
} from "@/lib/auth/token-store";

export type LoginResponse = {
  access?: string;
  role?: string;
  requires_2fa?: boolean;
  csrfToken?: string;
};

export async function login(email: string, password: string) {
  return apiFetch<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: { email, password },
    auth: false,
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

export function applyLogin(data: LoginResponse) {
  if (data.csrfToken) setCsrfToken(data.csrfToken);
  if (data.access) setAccessToken(data.access);
  if (data.role) setRole(data.role);
}
