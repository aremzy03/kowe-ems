"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PaymentsTable } from "@/components/finance/PaymentsTable";
import {
  Card,
  CardBody,
  EmptyState,
  Label,
  PageHeader,
  Select,
} from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";

function termOptionLabel(name?: string, session?: string) {
  return [session, name].filter(Boolean).join(" · ") || "Term";
}

function LedgerBody() {
  const searchParams = useSearchParams();
  const presetInvoice = searchParams.get("invoice") ?? "";
  const [status, setStatus] = useState("");
  const [termId, setTermId] = useState("");
  const [invoiceId, setInvoiceId] = useState(presetInvoice);

  useEffect(() => {
    setInvoiceId(presetInvoice);
  }, [presetInvoice]);

  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const payments = useQuery({
    queryKey: ["finance", "payments", invoiceId, status, termId],
    queryFn: () =>
      financeApi.listPayments({
        ...(invoiceId ? { invoice: invoiceId } : {}),
        ...(status ? { status } : {}),
        ...(termId ? { term: termId } : {}),
      }),
  });

  const termOptions = useMemo(() => {
    return (terms.data ?? []).map((term) => ({
      id: term.id,
      label: termOptionLabel(term.name, term.session_name),
    }));
  }, [terms.data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payment ledger"
        description="Every recorded payment in this school. Pending Paystack checkouts are listed but are not treated as paid."
      />

      <Card>
        <CardBody className="flex flex-wrap items-end gap-3">
          <div className="min-w-[10rem] flex-1">
            <Label htmlFor="ledger-status">Status</Label>
            <Select
              id="ledger-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="success">Success</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </Select>
          </div>
          <div className="min-w-[12rem] flex-1">
            <Label htmlFor="ledger-term">Term</Label>
            <Select
              id="ledger-term"
              value={termId}
              onChange={(e) => setTermId(e.target.value)}
            >
              <option value="">All terms</option>
              {termOptions.map((term) => (
                <option key={term.id} value={term.id}>
                  {term.label}
                </option>
              ))}
            </Select>
          </div>
          {invoiceId ? (
            <button
              type="button"
              className="text-sm font-medium text-ink underline"
              onClick={() => setInvoiceId("")}
            >
              Clear invoice filter
            </button>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-0">
          {payments.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading payments…</p>
          ) : payments.error ? (
            <p className="p-4 text-sm text-danger">
              {payments.error instanceof Error
                ? payments.error.message
                : "Failed to load payments"}
            </p>
          ) : (payments.data ?? []).length === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No payments match"
                body="Try another status or term, or record a cash payment from an invoice."
              />
            </div>
          ) : (
            <PaymentsTable payments={payments.data ?? []} showStudent />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export default function BursarPaymentsPage() {
  return (
    <Suspense
      fallback={<p className="text-sm text-ink/70">Loading payment ledger…</p>}
    >
      <LedgerBody />
    </Suspense>
  );
}
