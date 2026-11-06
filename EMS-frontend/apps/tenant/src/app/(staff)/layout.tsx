"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { StaffShell } from "@/components/layout/StaffShell";
import type { SchoolRole } from "@/lib/auth/token-store";

function roleForPath(pathname: string): SchoolRole[] {
  if (pathname.startsWith("/admin")) return ["admin"];
  if (pathname.startsWith("/teacher")) return ["teacher"];
  if (pathname.startsWith("/bursar")) return ["bursar"];
  return ["admin", "teacher", "bursar"];
}

export default function StaffLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const allow = roleForPath(pathname);

  return (
    <RoleGuard allow={allow}>
      <StaffShell>{children}</StaffShell>
    </RoleGuard>
  );
}
