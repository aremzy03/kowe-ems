"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CollectionsDashboard,
  collectionsPencilNote,
  type CollectionsDashboardData,
} from "@/components/finance/CollectionsDashboard";
import { EmptyState, PageHeader, PencilAside } from "@/components/ui";
import { academicsApi, currentTerm } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";
import { useAppSession } from "@/lib/auth/use-app-session";

export default function BursarHomePage() {
  const { displayName } = useAppSession();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = currentTerm(terms.data)?.id;
  const hasTerms = (terms.data?.length ?? 0) > 0;
  const collections = useQuery({
    queryKey: ["finance", "collections", termId],
    queryFn: () =>
      financeApi.collectionsDashboard(termId!) as Promise<CollectionsDashboardData>,
    enabled: Boolean(termId),
  });

  const note = collectionsPencilNote(collections.data);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome, ${displayName}`}
        description="Fee collection dashboard"
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline={hasTerms ? "No current term" : "No terms yet"}
          body={
            hasTerms
              ? "Set the current term in Academics. Collections use that term."
              : "Create an academic term before viewing collections."
          }
        />
      ) : (
        <>
          {note ? <PencilAside>{note}</PencilAside> : null}
          <CollectionsDashboard
            data={collections.data}
            isLoading={terms.isLoading || collections.isLoading}
            error={collections.error}
            ledger
          />
        </>
      )}
    </div>
  );
}
