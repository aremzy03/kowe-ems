"use client";

import { useState } from "react";
import { ApiRequestError, apiFetch } from "@/lib/api/client";
import { getTenantSlug } from "@/lib/api/tenant";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";

/**
 * Dev-only ping: POST /api/auth/verify/ tenant-scoped so Network shows
 * X-Tenant-Slug on the API host (not a per-school API hostname).
 */
export default function ApiPingPage() {
  const [result, setResult] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const slug =
    typeof window !== "undefined" ? getTenantSlug(window.location.hostname) : null;

  async function ping() {
    setBusy(true);
    setResult("");
    try {
      const data = await apiFetch<{ detail?: string }>("/api/auth/verify/", {
        method: "POST",
        body: { token: "ping-invalid-token" },
        auth: false,
        scope: "tenant",
      });
      setResult(`Unexpected OK: ${JSON.stringify(data)}`);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setResult(
          `status=${err.status} detail=${err.detail ?? ""} slug=${slug ?? "null"} data=${JSON.stringify(err.data)}`,
        );
      } else {
        setResult(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-10 text-ink">
      <PageHeader
        title="API ping"
        description="Tenant-scoped POST /api/auth/verify/ — check X-Tenant-Slug in Network."
      />
      <p className="mb-4 text-sm text-ink/70">
        Open this page on{" "}
        <code className="rounded border border-ink/20 bg-paper-tint px-1">
          {"{slug}.localhost:3000/dev/api-ping"}
        </code>
        . Derived slug: <strong>{slug ?? "(none)"}</strong>
      </p>
      <Button type="button" onClick={ping} disabled={busy || !slug}>
        {busy ? "Pinging…" : "Ping verify"}
      </Button>
      {!slug && (
        <p className="mt-3 text-sm text-accent-2">
          No tenant slug — use a school subdomain host.
        </p>
      )}
      {result && (
        <pre className="mt-6 overflow-auto rounded-[var(--radius-nb-sm)] border border-ink bg-paper-card p-4 text-xs">
          {result}
        </pre>
      )}
    </main>
  );
}
