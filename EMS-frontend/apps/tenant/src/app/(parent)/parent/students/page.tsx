"use client";

import Link from "next/link";
import { Card, CardBody, EmptyState, PageHeader } from "@/components/ui";
import { useParentChildren } from "@/lib/parent/children";

export default function ParentStudentsPage() {
  const { children, isLoading, error } = useParentChildren();

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Students"
        description="Children linked to your parent account"
        actions={
          <Link
            href="/link-student"
            className="text-sm font-semibold text-accent-1 underline"
          >
            Link student
          </Link>
        }
      />

      {isLoading ? <p className="text-sm text-ink/70">Loading…</p> : null}
      {error ? (
        <p className="text-sm text-danger">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      ) : null}

      {!isLoading && children.length === 0 ? (
        <EmptyState
          headline="No linked students"
          body="Redeem a school-issued linking code to connect your child."
          primaryAction={
            <Link
              href="/link-student"
              className="nb-interactive inline-block border-2 border-ink bg-accent-1 px-3 py-1.5 text-sm font-semibold text-paper-card shadow-nb"
            >
              Link student
            </Link>
          }
        />
      ) : (
        <ul className="space-y-3">
          {children.map((child) => (
            <li key={child.id}>
              <Card>
                <CardBody>
                  <p
                    className="font-bold"
                    style={{ fontFamily: "var(--font-heading)" }}
                  >
                    {child.name}
                  </p>
                  <p
                    className="text-sm text-ink/70"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {child.className || child.id}
                  </p>
                </CardBody>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
