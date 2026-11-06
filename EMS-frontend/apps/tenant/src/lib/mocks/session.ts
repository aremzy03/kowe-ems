export type MockRole =
  | "admin"
  | "teacher"
  | "bursar"
  | "parent"
  | "platform_admin";

export type MockUser = {
  id: string;
  email: string;
  name: string;
  role: MockRole;
  schoolName: string;
};

/** Cookie name read by middleware and client session helpers */
export const EMS_MOCK_ROLE_COOKIE = "ems_mock_role";

/** Platform mock redirects to apps/platform origin (no /platform routes here). */
const PLATFORM_ORIGIN =
  process.env.NEXT_PUBLIC_PLATFORM_ORIGIN ?? "http://platform.localhost:3001";

export const ROLE_HOME: Record<MockRole, string> = {
  admin: "/admin",
  teacher: "/teacher",
  bursar: "/bursar",
  parent: "/parent",
  platform_admin: PLATFORM_ORIGIN,
};

/** Path prefix → required role (school UI only; platform lives in apps/platform). */
export const PROTECTED_ROLE_PATHS: { prefix: string; role: MockRole }[] = [
  { prefix: "/admin", role: "admin" },
  { prefix: "/teacher", role: "teacher" },
  { prefix: "/bursar", role: "bursar" },
  { prefix: "/parent", role: "parent" },
];

export const MOCK_USERS: Record<MockRole, MockUser> = {
  admin: {
    id: "usr_admin_01",
    email: "admin@testacademy.ng",
    name: "Ngozi Adeyemi",
    role: "admin",
    schoolName: "Test Academy",
  },
  teacher: {
    id: "usr_teacher_01",
    email: "teacher@testacademy.ng",
    name: "Ibrahim Musa",
    role: "teacher",
    schoolName: "Test Academy",
  },
  bursar: {
    id: "usr_bursar_01",
    email: "bursar@testacademy.ng",
    name: "Funke Balogun",
    role: "bursar",
    schoolName: "Test Academy",
  },
  parent: {
    id: "usr_parent_01",
    email: "parent@example.ng",
    name: "Chinedu Okeke",
    role: "parent",
    schoolName: "Test Academy",
  },
  platform_admin: {
    id: "usr_platform_01",
    email: "ops@ems.ng",
    name: "Amina Bello",
    role: "platform_admin",
    schoolName: "EMS Platform",
  },
};

export const LOGIN_ROLE_OPTIONS: {
  role: MockRole;
  label: string;
  description: string;
}[] = [
  {
    role: "admin",
    label: "School Admin",
    description: "Operations, users, and school settings",
  },
  {
    role: "teacher",
    label: "Teacher",
    description: "Classes, scores, and attendance",
  },
  {
    role: "bursar",
    label: "Bursar",
    description: "Fees, invoices, and payments",
  },
  {
    role: "parent",
    label: "Parent",
    description: "Student progress and notices",
  },
  {
    role: "platform_admin",
    label: "Platform Admin",
    description: "Multi-tenant revenue and schools",
  },
];

export function isMockRole(value: string | undefined | null): value is MockRole {
  return (
    value === "admin" ||
    value === "teacher" ||
    value === "bursar" ||
    value === "parent" ||
    value === "platform_admin"
  );
}

export function getMockUser(role: MockRole): MockUser {
  return MOCK_USERS[role];
}

export function roleFromDemoEmail(email: string): MockRole | null {
  const normalized = email.trim().toLowerCase();
  const match = Object.values(MOCK_USERS).find((user) => user.email === normalized);
  return match?.role ?? null;
}
