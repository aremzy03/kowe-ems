import type { MockRole } from "./session";

export type StaffNavItem = {
  href: string;
  label: string;
};

export const STAFF_NAV: Record<"admin" | "teacher" | "bursar", StaffNavItem[]> = {
  admin: [
    { href: "/admin", label: "Dashboard" },
    { href: "/admin/academics", label: "Academics" },
    { href: "/admin/students", label: "Students" },
    { href: "/admin/enrollment", label: "Enrollment" },
    { href: "/admin/staff", label: "Staff" },
    { href: "/admin/assignments", label: "Assignments" },
    { href: "/admin/attendance", label: "Attendance" },
    { href: "/admin/fees", label: "Fees" },
  ],
  teacher: [
    { href: "/teacher", label: "Home" },
    { href: "/teacher/marks", label: "Mark entry" },
    { href: "/teacher/components", label: "Components" },
    { href: "/teacher/attendance", label: "Attendance" },
    { href: "/teacher/broadsheet", label: "Broadsheet" },
    { href: "/teacher/remarks", label: "Remarks" },
  ],
  bursar: [
    { href: "/bursar", label: "Dashboard" },
    { href: "/bursar/fee-structures", label: "Fee structures" },
    { href: "/bursar/invoices", label: "Invoices" },
    { href: "/bursar/invoices/generate", label: "Generate invoices" },
    { href: "/bursar/payments", label: "Payments" },
    { href: "/bursar/payments/manual", label: "Manual payment" },
    { href: "/bursar/payment-account", label: "Payment account" },
  ],
};

export const MOCK_SESSION_TERM = "2025/2026 · First Term";

export function isStaffRole(
  role: MockRole | null | undefined,
): role is "admin" | "teacher" | "bursar" {
  return role === "admin" || role === "teacher" || role === "bursar";
}

export function titleForPath(
  pathname: string,
  items: StaffNavItem[],
): string {
  const exact = items.find((item) => item.href === pathname);
  if (exact) return exact.label;
  const nested = items
    .filter((item) => item.href !== pathname && pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return nested?.label ?? items[0]?.label ?? "EMS";
}
