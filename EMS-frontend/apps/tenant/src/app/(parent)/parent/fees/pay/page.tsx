"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Money,
  PageHeader,
} from "@/components/ui";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

function balanceOf(invoice: {
  outstanding_amount?: string;
  amount_due?: string;
  total_amount?: string;
  amount_paid?: string;
}): number {
  if (invoice.outstanding_amount != null && invoice.outstanding_amount !== "") {
    const remaining = Number(invoice.outstanding_amount);
    return Number.isFinite(remaining) ? Math.max(0, remaining) : 0;
  }
  const due = Number(invoice.amount_due ?? invoice.total_amount ?? 0);
  const paid = Number(invoice.amount_paid ?? 0);
  return Math.max(0, due - paid);
}

function PayForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const invoiceId = searchParams.get("invoice");
  const invoiceIds = (searchParams.get("invoices") ?? "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
  const ids = invoiceId ? [invoiceId] : invoiceIds;
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: invoices = [], isLoading } = useQuery({
    queryKey: ["finance", "my-invoices"],
    queryFn: () => financeApi.myInvoices(),
  });

  const chosen = ids
    .map((id) => invoices.find((inv) => inv.id === id))
    .filter((inv) => inv != null);
  const payable = chosen.filter((inv) => balanceOf(inv) > 0);
  const total = payable.reduce((sum, inv) => sum + balanceOf(inv), 0);

  async function pay() {
    if (payable.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const res =
        payable.length === 1
          ? await financeApi.initializePayment({ invoice: payable[0].id })
          : await financeApi.initializePayment({
              invoices: payable.map((inv) => inv.id),
            });
      if (res.authorization_url) {
        window.location.assign(res.authorization_url);
        return;
      }
      router.push(
        `/parent/fees/result?status=failed&reason=${encodeURIComponent("No authorization URL")}`,
      );
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Initialize failed");
      }
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardBody>
          <p className="text-ink/70">Loading…</p>
        </CardBody>
      </Card>
    );
  }

  if (payable.length === 0 || total <= 0) {
    return (
      <Card>
        <CardBody className="space-y-3">
          <p className="text-ink/75">Nothing to pay for this selection.</p>
          <Link href="/parent/fees">
            <Button variant="secondary" size="sm">
              Back to fees
            </Button>
          </Link>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody className="space-y-4">
        <div>
          <p className="text-sm text-ink/70">Paying for</p>
          <ul className="mt-2 space-y-2">
            {payable.map((inv) => (
              <li key={inv.id} className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-bold" style={{ fontFamily: "var(--font-heading)" }}>
                    {inv.student_name ?? "Student"}
                  </p>
                  <p className="text-sm text-ink/70">
                    {[inv.session_name, inv.term_name].filter(Boolean).join(" · ") ||
                      "Invoice"}
                  </p>
                </div>
                <p className="font-semibold">
                  <Money amount={balanceOf(inv)} />
                </p>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-[var(--radius-nb)] border-[1.5px] border-ink bg-paper px-4 py-3">
          <p className="text-sm text-ink/70">Amount due</p>
          <p className="text-3xl font-bold">
            <Money amount={total} />
          </p>
        </div>

        <p className="text-sm text-ink/70">
          You will be redirected to Paystack. One charge covers every invoice
          listed above. Confirm the amount before continuing.
        </p>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <Button className="w-full" onClick={() => void pay()} disabled={busy}>
          {busy ? "Starting…" : "Continue to Paystack"}
        </Button>
        <Link
          href="/parent/fees"
          className="block text-center text-sm font-medium text-ink/70 underline"
        >
          Cancel
        </Link>
      </CardBody>
    </Card>
  );
}

export default function ParentFeesPayPage() {
  return (
    <div className="mx-auto w-full max-w-md">
      <PageHeader
        title="Confirm payment"
        description="Review amount before Paystack checkout"
      />
      <Suspense
        fallback={
          <Card>
            <CardBody>
              <p className="text-ink/70">Loading…</p>
            </CardBody>
          </Card>
        }
      >
        <PayForm />
      </Suspense>
    </div>
  );
}
