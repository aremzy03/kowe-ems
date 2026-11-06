import { apiFetch } from "@/lib/api/client";

/** DailyAttendance.Status choices. */
export type AttendanceStatus = "present" | "absent" | "late" | "excused";

export type RegisterStudent = {
  id: string;
  name: string;
  admission_number?: string;
};

export type ClassRegister = {
  students?: RegisterStudent[];
  dates?: string[];
  grid?: {
    student: RegisterStudent;
    cells: {
      date: string;
      status: string | null;
      remarks?: string;
    }[];
  }[];
};

export type BulkAttendanceUpsertBody = {
  class_level_id: string;
  arm_id: string;
  term_id: string;
  date: string;
  entries: {
    student_id: string;
    status: AttendanceStatus;
    remarks?: string;
  }[];
};

export type BulkUpsertResponse = {
  count?: number;
  succeeded?: number;
  failed?: number;
  results?: { success?: boolean; errors?: unknown }[];
};

export const attendanceApi = {
  register: (params: {
    class_level: string;
    arm: string;
    term: string;
    month?: string;
    date_from?: string;
    date_to?: string;
  }) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, value]) => Boolean(value)) as [
        string,
        string,
      ][],
    ).toString();
    return apiFetch<ClassRegister>(`/api/attendance/register/?${q}`, {
      auth: true,
    });
  },
  bulkUpsert: (body: BulkAttendanceUpsertBody) =>
    apiFetch<BulkUpsertResponse>("/api/attendance/daily/bulk-upsert/", {
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
