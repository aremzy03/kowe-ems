import { apiFetch } from "@/lib/api/client";
import type { Paginated } from "@/lib/api/academics";

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

export type AssessmentComponent = {
  id: string;
  name: string;
  weight: string | number;
  max_score?: string | number;
  subject?: string;
  class_level?: string;
  term?: string;
};

export const assessmentApi = {
  components: {
    list: async (qs = "") => {
      const data = await apiFetch<Paginated<AssessmentComponent> | AssessmentComponent[]>(
        `/api/assessment/components/${qs}`,
        { auth: true },
      );
      return unwrapList(data);
    },
  },
  setScheme: (body: unknown) =>
    apiFetch("/api/assessment/components/set-scheme/", {
      method: "POST",
      body,
      auth: true,
    }),
  myComponents: (params: {
    subject: string;
    class_level: string;
    term: string;
  }) => {
    const q = new URLSearchParams(params).toString();
    return apiFetch<AssessmentComponent[] | Paginated<AssessmentComponent>>(
      `/api/assessment/my-components/?${q}`,
      { auth: true },
    ).then(unwrapList);
  },
  bulkUpsertScores: (body: unknown) =>
    apiFetch("/api/assessment/scores/bulk-upsert/", {
      method: "POST",
      body,
      auth: true,
    }),
  recompute: (body: unknown) =>
    apiFetch("/api/assessment/results/recompute/", {
      method: "POST",
      body,
      auth: true,
    }),
  studentResults: (student: string, term: string) =>
    apiFetch(
      `/api/assessment/results/student/?student=${encodeURIComponent(student)}&term=${encodeURIComponent(term)}`,
      { auth: true },
    ),
  remarks: (body: unknown) =>
    apiFetch("/api/assessment/results/remarks/", {
      method: "POST",
      body,
      auth: true,
    }),
  broadsheet: (params: {
    class_level: string;
    arm: string;
    term: string;
    subject?: string;
  }) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][],
    ).toString();
    return apiFetch(`/api/assessment/broadsheet/?${q}`, { auth: true });
  },
  reportCardPdf: async (student: string, term: string) => {
    const { TENANT_API_URL } = await import("@/lib/api/config");
    const { getAccessToken } = await import("@/lib/auth/token-store");
    const { getTenantSlug } = await import("@/lib/api/tenant");
    const slug = getTenantSlug();
    if (!slug) throw new Error("Tenant identification required");
    const token = getAccessToken();
    const res = await fetch(
      `${TENANT_API_URL}/api/assessment/report-cards/?student=${encodeURIComponent(student)}&term=${encodeURIComponent(term)}`,
      {
        credentials: "include",
        headers: {
          Accept: "application/pdf",
          "X-Tenant-Slug": slug,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      },
    );
    if (!res.ok) throw new Error(`Report card failed (${res.status})`);
    return res.blob();
  },
};
