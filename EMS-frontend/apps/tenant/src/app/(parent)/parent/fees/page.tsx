"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardBody,
  Money,
  PageHeader,
} from "@/components/ui";
import { financeApi, type Invoice } from "@/lib/api/finance";
import { useParentChildren } from "@/lib/parent/children";

function feeVariant(status?: string): "success" | "warning" | "danger" | "info" {
  const s = (status ?? "").toLowerCase();
  if (s.includes("paid") && !s.includes("un")) return "success";
  if (s.includes("partial")) return "warning";
  if (s.includes("overdue")) return "danger";
  return "info";
}

function balanceOf(inv: Invoice): number {
  const due = Number(inv.amount_due ?? 0);
  const paid = Number(inv.amount_paid ?? 0);
  return Math.max(0, due - paid);
}

export default function ParentFeesPage() {
  const { selected } = useParentChildren();
  const { data: invoices = [], isLoading, error } = useQuery({
    queryKey: ["finance", "my-invoices"],
    queryFn: () => financeApi.myInvoices(),
  });

  const filtered = selected
    ? invoices.filter((inv) => !inv.student || inv.student === selected.id)
    : invoices;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Fees"
        description={
          selected
            ? `${selected.name} · invoices and balances`
            : "Select a linked child to view fees"
        }
      />

      {isLoading ? (
        <p className="text-sm text-ink/70">Loading invoices…</p>
      ) : null}
      {error ? (
        <p className="text-sm text-danger">
          {error instanceof Error ? error.message : "Failed to load invoices"}
        </p>
      ) : null}

      {!isLoading && filtered.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-ink/75">No invoices for this child.</p>
          </CardBody>
        </Card>
      ) : (
        <ul className="space-y-3">
          {filtered.map((inv) => {
            const balance = balanceOf(inv);
            return (
              <li key={inv.id}>
                <Card>
                  <CardBody className="space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p
                          className="font-bold"
                          style={{ fontFamily: "var(--font-mono)" }}
                        >
                          {inv.reference ?? inv.id}
                        </p>
                      </div>
                      <Badge variant={feeVariant(inv.status)}>
                        {inv.status ?? "—"}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap items-end justify-between gap-3">
                      <div>
                        <p className="text-sm text-ink/70">Amount due</p>
                        <p className="font-semibold">
                          <Money amount={Number(inv.amount_due ?? 0)} />
                        </p>
                        <p className="mt-1 text-sm text-ink/70">Balance</p>
                        <p className="text-lg font-bold">
                          <Money amount={balance} />
                        </p>
                      </div>
                      {balance > 0 ? (
                        <Link href={`/parent/fees/pay?invoice=${inv.id}`}>
                          <Button size="sm">Pay</Button>
                        </Link>
                      ) : null}
                    </div>
                  </CardBody>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
