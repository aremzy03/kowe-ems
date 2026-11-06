import Link from "next/link";
import { EmptyState, Button } from "@/components/ui";

export default function ForbiddenPage() {
  return (
    <main
      className="flex min-h-screen items-center justify-center bg-paper px-4 py-12 text-ink"
      style={{
        backgroundImage:
          "radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--color-ink) 8%, transparent) 1px, transparent 0)",
        backgroundSize: "12px 12px",
      }}
    >
      <EmptyState
        headline="Access denied"
        body="Your mock role cannot open this area of Test Academy. Switch role or return home."
        primaryAction={
          <Link href="/login">
            <Button>Switch role</Button>
          </Link>
        }
        secondaryAction={
          <Link href="/">
            <Button variant="secondary">Portal home</Button>
          </Link>
        }
      />
    </main>
  );
}
