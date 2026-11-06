"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CollectionsDashboard,
  type CollectionsDashboardData,
} from "@/components/finance/CollectionsDashboard";
import { EmptyState, PageHeader } from "@/components/ui";
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
    queryFn: () =>
      financeApi.collectionsDashboard(termId!) as Promise<CollectionsDashboardData>,
    enabled: Boolean(termId),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Bursar · ${displayName}`}
        description="Fee collection dashboard"
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline="No terms yet"
          body="Create an academic term before viewing collections."
        />
      ) : (
        <CollectionsDashboard
          data={collections.data}
          isLoading={terms.isLoading || collections.isLoading}
          error={collections.error}
        />
      )}
    </div>
  );
}
