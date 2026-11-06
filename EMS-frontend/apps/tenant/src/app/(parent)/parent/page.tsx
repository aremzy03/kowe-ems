"use client";

import Link from "next/link";
import { Card, CardBody, PageHeader } from "@/components/ui";
import { useParentChildren } from "@/lib/parent/children";
import { useAppSession } from "@/lib/auth/use-app-session";

const HOME_LINKS = [
  {
    href: "/parent/results",
    label: "Results",
    hint: "Published term scores and report cards",
  },
  {
    href: "/parent/attendance",
    label: "Attendance",
    hint: "Present, absent, and late days",
  },
  {
    href: "/parent/fees",
    label: "Fees",
    hint: "Balances, invoices, and payment status",
  },
] as const;

export default function ParentHomePage() {
  const { displayName } = useAppSession();
  const { children, selected, isLoading } = useParentChildren();

  const description = selected
    ? `Quick links for ${selected.name}`
    : children.length > 0
      ? "Choose a child above, then open results, attendance, or fees."
      : "Link a student with a school-issued code to get started.";

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <PageHeader
        title={displayName ? `Hello, ${displayName}` : "Home"}
        description={description}
      />
      {isLoading ? <p className="text-sm text-ink/70">Loading…</p> : null}
      <Card>
        <CardBody className="divide-y divide-ink/10 p-0">
          {HOME_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-baseline justify-between gap-4 px-5 py-4 transition-colors hover:bg-paper-tint/60"
            >
              <span
                className="font-bold"
                style={{ fontFamily: "var(--font-heading)" }}
              >
                {item.label}
              </span>
              <span className="text-right text-sm text-ink/65">{item.hint}</span>
            </Link>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
