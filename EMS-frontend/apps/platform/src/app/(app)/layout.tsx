"use client";

import type { ReactNode } from "react";
import { PlatformShell } from "@/components/layout/PlatformShell";

/** Authenticated platform routes (revenue, tenants, webhooks). Login is outside this group. */
export default function AppSectionLayout({ children }: { children: ReactNode }) {
  return <PlatformShell>{children}</PlatformShell>;
}
