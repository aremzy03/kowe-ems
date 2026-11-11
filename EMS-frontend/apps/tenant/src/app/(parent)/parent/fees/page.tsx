"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
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
  if (inv.outstanding_amount != null && inv.outstanding_amount !== "") {
    const remaining = Number(inv.outstanding_amount);
    return Number.isFinite(remaining) ? Math.max(0, remaining) : 0;
  }
  const due = Number(inv.amount_due ?? inv.total_amount ?? 0);
  const paid = Number(inv.amount_paid ?? 0);
  return Math.max(0, due - paid);
}

export default function ParentFeesPage() {
  const { selected } = useParentChildren();
  const { data: invoices = [], isLoading, error } = useQuery({
    queryKey: ["finance", "my-invoices"],
    queryFn: () => financeApi.myInvoices(),
  });
  const [picked, setPicked] = useState<string[]>([]);

  const openInvoices = useMemo(
    () => invoices.filter((inv) => balanceOf(inv) > 0),
    [invoices],
  );
  const selectedInvoices = openInvoices.filter((inv) => picked.includes(inv.id));
  const selectedTotal = selectedInvoices.reduce(
    (sum, inv) => sum + balanceOf(inv),
    0,
  );

  function toggle(id: string) {
    setPicked((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  const payHref =
    selectedInvoices.length === 1
      ? `/parent/fees/pay?invoice=${selectedInvoices[0].id}`
      : `/parent/fees/pay?invoices=${selectedInvoices.map((inv) => inv.id).join(",")}`;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Fees"
        description={
          selected
            ? `Invoices for your linked children. ${selected.name} is selected above.`
            : "Invoices for your linked children. Select more than one to pay them together."
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

      {selectedInvoices.length > 0 ? (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm text-ink/70">
                {selectedInvoices.length === 1
                  ? "1 invoice selected"
                  : `${selectedInvoices.length} invoices selected`}
              </p>
              <p className="text-lg font-bold">
                <Money amount={selectedTotal} />
              </p>
            </div>
            <Link href={payHref}>
              <Button size="sm">
                {selectedInvoices.length > 1 ? "Pay together" : "Pay selected"}
              </Button>
            </Link>
          </CardBody>
        </Card>
      ) : null}

      {!isLoading && invoices.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-ink/75">No invoices for your linked children.</p>
          </CardBody>
        </Card>
      ) : (
        <ul className="space-y-3">
          {invoices.map((inv) => {
            const balance = balanceOf(inv);
            const chargeName = inv.line_items
              ?.map((item) => item.name)
              .filter(Boolean)
              .join(", ");
            return (
              <li key={inv.id}>
                <Card>
                  <CardBody className="space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-bold" style={{ fontFamily: "var(--font-heading)" }}>
                          {inv.student_name ?? "Student"}
                        </p>
                        <p className="text-sm text-ink/70">
                          {[inv.session_name, inv.term_name].filter(Boolean).join(" · ") ||
                            "Invoice"}
                          {chargeName ? ` · ${chargeName}` : ""}
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
                          <Money
                            amount={Number(inv.total_amount ?? inv.amount_due ?? 0)}
                          />
                        </p>
                        <p className="mt-1 text-sm text-ink/70">Balance</p>
                        <p className="text-lg font-bold">
                          <Money amount={balance} />
                        </p>
                      </div>
                      {balance > 0 ? (
                        <label className="flex items-center gap-2 text-sm font-medium">
                          <input
                            type="checkbox"
                            checked={picked.includes(inv.id)}
                            onChange={() => toggle(inv.id)}
                          />
                          Include
                        </label>
                      ) : null}
                    </div>
                    {(inv.payments ?? []).length > 0 ? (
                      <ul className="space-y-1 border-t border-ink/15 pt-3 text-sm">
                        {(inv.payments ?? []).map((payment) => (
                          <li
                            key={payment.id}
                            className="flex flex-wrap justify-between gap-2 text-ink/80"
                          >
                            <span>
                              {payment.status === "success"
                                ? "Paid"
                                : payment.status === "pending"
                                  ? "Pending"
                                  : payment.status === "failed"
                                    ? "Failed"
                                    : payment.status}{" "}
                              ·{" "}
                              {payment.gateway === "manual"
                                ? payment.method === "bank_transfer"
                                  ? "Bank transfer"
                                  : "Cash"
                                : "Paystack"}
                            </span>
                            <span style={{ fontFamily: "var(--font-mono)" }}>
                              <Money amount={Number(payment.amount ?? 0)} />
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
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
