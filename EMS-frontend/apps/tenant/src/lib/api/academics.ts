import { apiFetch } from "@/lib/api/client";

export type Paginated<T> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results: T[];
};

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function listResource<T>(path: string): Promise<T[]> {
  const data = await apiFetch<Paginated<T> | T[]>(path, { auth: true });
  return unwrapList(data);
}

export type Session = {
  id: string;
  name: string;
  start_date?: string;
  end_date?: string;
  is_active?: boolean;
};

export type Term = {
  id: string;
  name: string;
  session: string;
  session_name?: string;
  start_date?: string;
  end_date?: string;
  total_school_days?: number;
  is_active?: boolean;
};

export type ClassLevel = { id: string; name: string; order?: number };
export type Arm = { id: string; name: string; class_level: string };
export type Subject = { id: string; name: string; code?: string };
export type Student = {
  id: string;
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: string;
  admission_number?: string;
  admission_date?: string;
  full_name?: string;
  linking_code?: string | null;
};
export type Enrollment = {
  id: string;
  student: string;
  student_name?: string;
  student_admission_number?: string;
  term: string;
  term_name?: string;
  class_level: string;
  class_level_name?: string;
  arm: string;
  arm_name?: string;
  session?: string;
  session_name?: string;
  status?: string;
};
export type ClassSubjectAssignment = {
  id: string;
  teacher: string;
  teacher_email?: string;
  subject: string;
  subject_name?: string;
  subject_code?: string;
  class_level: string;
  class_level_name?: string;
  arm: string;
  arm_name?: string;
  term: string;
  term_name?: string;
};
export type ClassTeacherAssignment = {
  id: string;
  teacher: string;
  teacher_email?: string;
  class_level: string;
  class_level_name?: string;
  arm: string;
  arm_name?: string;
  term: string;
  term_name?: string;
};

export const academicsApi = {
  sessions: {
    list: () => listResource<Session>("/api/academics/sessions/"),
    create: (body: Partial<Session>) =>
      apiFetch<Session>("/api/academics/sessions/", {
        method: "POST",
        body,
        auth: true,
      }),
    update: (id: string, body: Partial<Session>) =>
      apiFetch<Session>(`/api/academics/sessions/${id}/`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    remove: (id: string) =>
      apiFetch(`/api/academics/sessions/${id}/`, {
        method: "DELETE",
        auth: true,
      }),
  },
  terms: {
    list: () => listResource<Term>("/api/academics/terms/"),
    create: (body: Partial<Term>) =>
      apiFetch<Term>("/api/academics/terms/", {
        method: "POST",
        body,
        auth: true,
      }),
    update: (id: string, body: Partial<Term>) =>
      apiFetch<Term>(`/api/academics/terms/${id}/`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    remove: (id: string) =>
      apiFetch(`/api/academics/terms/${id}/`, {
        method: "DELETE",
        auth: true,
      }),
  },
  classLevels: {
    list: () => listResource<ClassLevel>("/api/academics/class-levels/"),
    create: (body: Partial<ClassLevel>) =>
      apiFetch<ClassLevel>("/api/academics/class-levels/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  arms: {
    list: () => listResource<Arm>("/api/academics/arms/"),
    create: (body: Partial<Arm>) =>
      apiFetch<Arm>("/api/academics/arms/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  subjects: {
    list: () => listResource<Subject>("/api/academics/subjects/"),
    create: (body: Partial<Subject>) =>
      apiFetch<Subject>("/api/academics/subjects/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  students: {
    list: () => listResource<Student>("/api/academics/students/"),
    create: (body: Partial<Student>) =>
      apiFetch<Student>("/api/academics/students/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  enrollments: {
    list: () => listResource<Enrollment>("/api/academics/enrollments/"),
    create: (body: Partial<Enrollment>) =>
      apiFetch<Enrollment>("/api/academics/enrollments/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  classSubjectAssignments: {
    list: () =>
      listResource<ClassSubjectAssignment>(
        "/api/academics/class-subject-assignments/",
      ),
    create: (body: Partial<ClassSubjectAssignment>) =>
      apiFetch<ClassSubjectAssignment>(
        "/api/academics/class-subject-assignments/",
        { method: "POST", body, auth: true },
      ),
  },
  classTeacherAssignments: {
    list: () =>
      listResource<ClassTeacherAssignment>(
        "/api/academics/class-teacher-assignments/",
      ),
    create: (body: Partial<ClassTeacherAssignment>) =>
      apiFetch<ClassTeacherAssignment>(
        "/api/academics/class-teacher-assignments/",
        { method: "POST", body, auth: true },
      ),
  },
  myStudents: () =>
    listResource<Student>("/api/academics/my-students/").catch(async () => {
      const data = await apiFetch<Paginated<Student> | Student[]>(
        "/api/academics/my-students/",
        { auth: true },
      );
      return unwrapList(data);
    }),
  myStudent: (id: string) =>
    apiFetch<Student>(`/api/academics/my-students/${id}/`, { auth: true }),
  myAssignments: () =>
    listResource<ClassSubjectAssignment>("/api/academics/my-assignments/"),
  myClasses: () =>
    listResource<ClassTeacherAssignment>("/api/academics/my-classes/"),
  redeemLinkingCode: (code: string, relationship_to_student = "guardian") =>
    apiFetch<{ detail?: string; student_id?: string }>(
      "/api/academics/linking-codes/redeem/",
      {
        method: "POST",
        body: { code, relationship_to_student },
        auth: true,
      },
    ),
  createInvite: (email: string, role: string) =>
    apiFetch("/api/memberships/invites/", {
      method: "POST",
      body: { email, role },
      auth: true,
    }),
};
