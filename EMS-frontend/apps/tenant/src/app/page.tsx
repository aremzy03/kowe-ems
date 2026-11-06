import Link from "next/link";
import { KoweLockup } from "@/components/layout/KoweLockup";
import { PLATFORM_ORIGIN } from "@/lib/api/config";

const portals = [
  {
    href: "/admin",
    title: "Admin",
    description: "School operations, users, and configuration.",
  },
  {
    href: "/teacher",
    title: "Teacher",
    description: "Classes, assessments, and attendance.",
  },
  {
    href: "/bursar",
    title: "Bursar",
    description: "Fees, invoices, and payments.",
  },
  {
    href: "/parent",
    title: "Parent",
    description: "Student progress and school notices.",
  },
  {
    href: "/login",
    title: "Login",
    description: "Sign in to your school workspace.",
  },
] as const;

export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-12 text-ink md:px-10">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4">
          <KoweLockup width={240} className="mx-0" />
        </div>
        <p className="mb-10 max-w-2xl text-base leading-relaxed text-ink/75">
          School portals on this subdomain. Platform operators use a separate
          app host.
        </p>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {portals.map((portal) => (
            <Link
              key={portal.href}
              href={portal.href}
              className="block rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card p-5 transition-colors hover:bg-paper-tint"
            >
              <h2
                className="mb-2 text-xl font-bold"
                style={{ fontFamily: "var(--font-heading)" }}
              >
                {portal.title}
              </h2>
              <p className="mb-4 text-sm leading-relaxed text-ink/70">
                {portal.description}
              </p>
              <span
                className="nb-interactive inline-block border-2 border-ink bg-accent-1 px-3 py-1 text-sm font-semibold text-paper-card shadow-nb-sm"
                style={{ fontFamily: "var(--font-heading)" }}
              >
                Open {portal.href}
              </span>
            </Link>
          ))}
          <a
            href={PLATFORM_ORIGIN}
            className="block rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card p-5 transition-colors hover:bg-paper-tint"
          >
            <h2
              className="mb-2 text-xl font-bold"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              Platform
            </h2>
            <p className="mb-4 text-sm leading-relaxed text-ink/70">
              Multi-tenant platform controls (separate Next app).
            </p>
            <span
              className="nb-interactive inline-block border-2 border-ink bg-accent-1 px-3 py-1 text-sm font-semibold text-paper-card shadow-nb-sm"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              Open {PLATFORM_ORIGIN}
            </span>
          </a>
        </div>
      </div>
    </main>
  );
}
