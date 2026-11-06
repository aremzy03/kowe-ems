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
import { useParentChildren } from "@/lib/parent/children";

function PayForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const invoiceId = searchParams.get("invoice");
  const { selected } = useParentChildren();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: invoices = [], isLoading } = useQuery({
    queryKey: ["finance", "my-invoices"],
    queryFn: () => financeApi.myInvoices(),
  });

  const invoice = invoices.find((inv) => inv.id === invoiceId);
  const due = Number(invoice?.amount_due ?? 0);
  const paid = Number(invoice?.amount_paid ?? 0);
  const balance = Math.max(0, due - paid);

  async function pay() {
    if (!invoice) return;
    setBusy(true);
    setError(null);
    try {
      const res = await financeApi.initializePayment({ invoice: invoice.id });
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

  if (!selected || !invoice || balance <= 0) {
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
          <p className="font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            {selected.name}
          </p>
          <p
            className="text-sm text-ink/70"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {invoice.reference ?? invoice.id}
          </p>
        </div>

        <div className="rounded-[var(--radius-nb)] border-[1.5px] border-ink bg-paper px-4 py-3">
          <p className="text-sm text-ink/70">Amount due</p>
          <p className="text-3xl font-bold">
            <Money amount={balance} />
          </p>
        </div>

        <p className="text-sm text-ink/70">
          You will be redirected to Paystack. Confirm the amount before continuing.
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
