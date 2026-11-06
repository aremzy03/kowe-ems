"use client";

import type { ReactNode } from "react";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { ParentShell } from "@/components/layout/ParentShell";
import { ParentChildrenProvider } from "@/lib/parent/children";

export default function ParentGroupLayout({ children }: { children: ReactNode }) {
  return (
    <RoleGuard allow={["parent"]}>
      <ParentChildrenProvider>
        <ParentShell>{children}</ParentShell>
      </ParentChildrenProvider>
    </RoleGuard>
  );
}
