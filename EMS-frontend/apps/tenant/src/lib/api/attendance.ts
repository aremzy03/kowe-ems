import { apiFetch } from "@/lib/api/client";

export const attendanceApi = {
  register: (params: {
    class_level: string;
    arm: string;
    term: string;
    month: string;
  }) => {
    const q = new URLSearchParams(params).toString();
    return apiFetch(`/api/attendance/register/?${q}`, { auth: true });
  },
  bulkUpsert: (body: unknown) =>
    apiFetch("/api/attendance/daily/bulk-upsert/", {
      method: "POST",
      body,
      auth: true,
    }),
  studentSummary: (student: string, term: string) =>
    apiFetch(
      `/api/attendance/summaries/student/?student=${encodeURIComponent(student)}&term=${encodeURIComponent(term)}`,
      { auth: true },
    ),
  parentDaily: (student: string, term: string) =>
    apiFetch(
      `/api/attendance/parents/daily/?student=${encodeURIComponent(student)}&term=${encodeURIComponent(term)}`,
      { auth: true },
    ),
  adminOverview: (params: { date?: string; term?: string }) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][],
    ).toString();
    return apiFetch(`/api/attendance/admin/overview/?${q}`, { auth: true });
  },
};
