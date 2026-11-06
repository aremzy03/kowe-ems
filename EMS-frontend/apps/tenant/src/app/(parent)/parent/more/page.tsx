"use client";

import Link from "next/link";
import { Button, Card, CardBody, PageHeader } from "@/components/ui";
import { useAppSession } from "@/lib/auth/use-app-session";

const MORE_LINKS = [
  { href: "/parent/students", label: "Linked students" },
  { href: "/parent/attendance", label: "Attendance" },
  { href: "/parent/results", label: "Results" },
  { href: "/parent/fees", label: "Fees" },
  { href: "/link-student", label: "Link another student" },
] as const;

export default function ParentMorePage() {
  const { displayName, schoolName, logout } = useAppSession();

  return (
    <div className="mx-auto w-full max-w-5xl">
      <PageHeader
        title="More"
        description="Account, linking, and session controls"
      />
      <Card>
        <CardBody className="space-y-4">
          <div>
            <p
              className="font-bold"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              {displayName}
            </p>
            <p className="text-sm text-ink/70">{schoolName}</p>
          </div>
          <ul className="space-y-2">
            {MORE_LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="flex rounded-[var(--radius-nb-sm)] border border-ink/20 bg-paper px-4 py-2.5 text-sm font-semibold hover:bg-paper-tint"
                  style={{ fontFamily: "var(--font-heading)" }}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div>
            <Button variant="secondary" onClick={() => void logout()}>
              Log out
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
