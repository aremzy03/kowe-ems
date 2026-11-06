"use client";

import Link from "next/link";
import { Card, CardBody, PageHeader } from "@/components/ui";
import { useParentChildren } from "@/lib/parent/children";
import { useAppSession } from "@/lib/auth/use-app-session";

export default function ParentHomePage() {
  const { displayName } = useAppSession();
  const { children, selected, isLoading } = useParentChildren();

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <PageHeader
        title={`Hello, ${displayName}`}
        description={
          selected
            ? `Viewing ${selected.name}`
            : "Link a student to get started"
        }
      />
      {isLoading ? <p className="text-sm text-ink/70">Loading…</p> : null}
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { href: "/parent/results", label: "Results" },
          { href: "/parent/attendance", label: "Attendance" },
          { href: "/parent/fees", label: "Fees" },
        ].map((item) => (
          <Link key={item.href} href={item.href}>
            <Card>
              <CardBody>
                <p
                  className="font-bold"
                  style={{ fontFamily: "var(--font-heading)" }}
                >
                  {item.label}
                </p>
                <p className="text-sm text-ink/65">
                  {children.length} linked student(s)
                </p>
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
