"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CollectionsDashboard,
  type CollectionsDashboardData,
} from "@/components/finance/CollectionsDashboard";
import { FeeStructuresPanel } from "@/components/finance/FeeStructuresPanel";
import { EmptyState, PageHeader } from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";

export default function AdminFeesPage() {
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = terms.data?.[0]?.id;
  const collections = useQuery({
    queryKey: ["finance", "collections", termId],
    queryFn: () =>
      financeApi.collectionsDashboard(termId!) as Promise<CollectionsDashboardData>,
    enabled: Boolean(termId),
  });

  return (
    <div className="space-y-8">
      <PageHeader
        title="Fees"
        description="Collections overview and fee structures"
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline="No terms yet"
          body="Create an academic term before viewing fee collections."
        />
      ) : (
        <section className="space-y-3">
          <h2
            className="text-lg font-bold tracking-tight"
            style={{ fontFamily: "var(--font-heading)" }}
          >
            Collections
          </h2>
          <CollectionsDashboard
            data={collections.data}
            isLoading={terms.isLoading || collections.isLoading}
            error={collections.error}
          />
        </section>
      )}

      <FeeStructuresPanel />
    </div>
  );
}
