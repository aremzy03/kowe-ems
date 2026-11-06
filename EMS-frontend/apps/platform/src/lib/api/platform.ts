import { apiFetch } from "@/lib/api/client";

export type PlatformTenant = {
  id: string;
  school_name: string;
  schema_name: string;
  slug: string;
  primary_domain: string | null;
  is_active: boolean;
  created_at: string;
};

export type PlatformTenantList = {
  count: number;
  results: PlatformTenant[];
};

export type PlatformWebhookLog = {
  id: string;
  received_at: string;
  signature_valid: boolean;
  event: string;
  reference: string;
  subaccount_code: string;
  school_name: string | null;
  outcome: string;
  error_message: string;
  payload_preview: string;
};

export type PlatformWebhookList = {
  count: number;
  results: PlatformWebhookLog[];
};

export async function fetchTenants() {
  return apiFetch<PlatformTenantList>("/api/platform/tenants/", {
    auth: true,
    scope: "platform",
  });
}

export async function fetchWebhookLogs() {
  return apiFetch<PlatformWebhookList>("/api/platform/webhooks/", {
    auth: true,
    scope: "platform",
  });
}
