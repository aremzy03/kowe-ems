"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardBody, PageHeader } from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";
import { useAppSession } from "@/lib/auth/use-app-session";

export default function BursarHomePage() {
  const { displayName } = useAppSession();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = terms.data?.[0]?.id;
  const collections = useQuery({
    queryKey: ["finance", "collections", termId],
    queryFn: () => financeApi.collectionsDashboard(termId!),
    enabled: Boolean(termId),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Bursar · ${displayName}`}
        description="Fee collection dashboard"
      />
      <Card>
        <CardBody>
          {collections.isLoading ? (
            <p className="text-sm text-ink/70">Loading…</p>
          ) : collections.error ? (
            <p className="text-sm text-danger">
              {collections.error instanceof Error
                ? collections.error.message
                : "Failed"}
            </p>
          ) : (
            <pre
              className="overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(collections.data ?? {}, null, 2)}
            </pre>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
