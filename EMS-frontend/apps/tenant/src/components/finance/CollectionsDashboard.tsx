"use client";

import {
  Card,
  CardBody,
  EmptyState,
  KpiCard,
  Money,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { formatNaira } from "@/lib/format-money";

/** Bucket fields shared by overall and by_class rows from collections API. */
export type CollectionsBucket = {
  invoiced_total?: string | number;
  collected_total?: string | number;
  outstanding_total?: string | number;
  collection_rate?: string | number;
  invoice_count?: number;
  paid_count?: number;
  partially_paid_count?: number;
  unpaid_count?: number;
};

export type CollectionsByClassRow = CollectionsBucket & {
  class_level_id?: string | null;
  class_level_name?: string;
};

export type CollectionsDashboardData = CollectionsBucket & {
  term?: {
    id?: string;
    name?: string;
    session?: string;
    is_active?: boolean;
  };
  by_class?: CollectionsByClassRow[];
};

export type CollectionsDashboardProps = {
  data?: CollectionsDashboardData | null;
  isLoading?: boolean;
  error?: Error | unknown | null;
  /** When true, skip the outer empty/loading wrappers used by full pages. */
  compact?: boolean;
  /** Coral margin on the class ledger. One sheet per view. */
  ledger?: boolean;
};

function moneyNumber(value?: string | number): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function rateLabel(value?: string | number): string {
  const n = moneyNumber(value);
  return `${n.toFixed(2)}%`;
}

function countPhrase(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** Outstanding-fee fact, or null when nothing is unpaid. */
export function collectionsPencilNote(
  data?: CollectionsDashboardData | null,
): string | null {
  if (!data) return null;
  const unpaid = data.unpaid_count ?? 0;
  const outstanding = moneyNumber(data.outstanding_total);
  if (outstanding <= 0 && unpaid <= 0) return null;
  if (outstanding > 0 && unpaid > 0) {
    return `${formatNaira(outstanding)} is still outstanding on ${countPhrase(unpaid, "unpaid invoice", "unpaid invoices")}.`;
  }
  if (outstanding > 0) {
    return `${formatNaira(outstanding)} is still outstanding this term.`;
  }
  return `${countPhrase(unpaid, "unpaid invoice remains", "unpaid invoices remain")} this term.`;
}

export function CollectionsDashboard({
  data,
  isLoading,
  error,
  compact = false,
  ledger = false,
}: CollectionsDashboardProps) {
  if (isLoading) {
    return <p className="text-sm text-ink/70">Loading collections…</p>;
  }

  if (error) {
    return (
      <p className="text-sm text-danger">
        {error instanceof Error ? error.message : "Failed to load collections"}
      </p>
    );
  }

  if (!data) {
    if (compact) return null;
    return (
      <EmptyState
        headline="No collection data"
        body="Pick an active term or generate invoices to see collection metrics."
      />
    );
  }

  const byClass = data.by_class ?? [];
  const termLabel = [data.term?.session, data.term?.name]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-4">
      {termLabel ? (
        <p className="text-sm text-ink/65">
          Term{" "}
          <span style={{ fontFamily: "var(--font-mono)" }}>{termLabel}</span>
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="Invoiced"
          value={formatNaira(moneyNumber(data.invoiced_total))}
        />
        <KpiCard
          label="Collected"
          value={formatNaira(moneyNumber(data.collected_total))}
          tone="green"
        />
        <KpiCard
          label="Outstanding"
          value={formatNaira(moneyNumber(data.outstanding_total))}
          tone="coral"
        />
        <KpiCard
          label="Collection rate"
          value={rateLabel(data.collection_rate)}
          rate={moneyNumber(data.collection_rate)}
          rateTone="green"
        />
        <KpiCard
          label="Invoices"
          value={String(data.invoice_count ?? 0)}
          delta={`Paid ${data.paid_count ?? 0} · Partial ${data.partially_paid_count ?? 0} · Unpaid ${data.unpaid_count ?? 0}`}
        />
      </div>

      <Card ledger={ledger}>
        <CardBody className="p-0">
          <Table className="border-0 shadow-none">
            <THead>
              <TR>
                <TH>Class</TH>
                <TH>Invoiced</TH>
                <TH>Collected</TH>
                <TH>Outstanding</TH>
                <TH>Rate</TH>
                <TH>Invoices</TH>
              </TR>
            </THead>
            <TBody>
              {byClass.length === 0 ? (
                <TR>
                  <TD colSpan={6} className="text-sm text-ink/65">
                    No invoices for this term yet.
                  </TD>
                </TR>
              ) : (
                byClass.map((row, i) => (
                  <TR key={row.class_level_id ?? row.class_level_name ?? i}>
                    <TD className="font-medium">
                      {row.class_level_name ?? "Unassigned"}
                    </TD>
                    <TD>
                      <Money amount={moneyNumber(row.invoiced_total)} />
                    </TD>
                    <TD>
                      <Money amount={moneyNumber(row.collected_total)} />
                    </TD>
                    <TD>
                      <Money amount={moneyNumber(row.outstanding_total)} />
                    </TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {rateLabel(row.collection_rate)}
                    </TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {row.invoice_count ?? 0}
                    </TD>
                  </TR>
                ))
              )}
            </TBody>
          </Table>
        </CardBody>
      </Card>
    </div>
  );
}
