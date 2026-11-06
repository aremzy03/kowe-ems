"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Input,
  Label,
  Money,
  PageHeader,
  Select,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { financeApi, type Invoice } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";
import { formatNaira } from "@/lib/format-money";

function moneyAmount(value?: string): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function invoiceLabel(inv: Invoice): string {
  const who = inv.student_name || "Student";
  const admission = inv.admission_number ? ` (${inv.admission_number})` : "";
  const term = [inv.session_name, inv.term_name].filter(Boolean).join(" ");
  const due = formatNaira(moneyAmount(inv.outstanding_amount ?? inv.total_amount));
  return [who + admission, term, `${due} outstanding`].filter(Boolean).join(" · ");
}

function ManualPaymentForm() {
  const searchParams = useSearchParams();
  const presetInvoice = searchParams.get("invoice") ?? "";
  const appliedPreset = useRef(false);
  const qc = useQueryClient();

  const invoices = useQuery({
    queryKey: ["finance", "invoices"],
    queryFn: () => financeApi.listInvoices(),
  });

  const [invoice, setInvoice] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chooseInvoice = useCallback((id: string, rows: Invoice[]) => {
    setInvoice(id);
    const row = rows.find((item) => item.id === id);
    const due = row?.outstanding_amount ?? "";
    setAmount(due && due !== "0.00" ? due : "");
  }, []);

  useEffect(() => {
    if (appliedPreset.current || !presetInvoice) return;
    const rows = invoices.data ?? [];
    if (!rows.some((row) => row.id === presetInvoice)) return;
    appliedPreset.current = true;
    chooseInvoice(presetInvoice, rows);
  }, [presetInvoice, invoices.data, chooseInvoice]);

  const selected = (invoices.data ?? []).find((row) => row.id === invoice);

  const save = useMutation({
    mutationFn: () =>
      financeApi.manualPayment({
        invoice,
        amount,
        method,
        notes: reference,
      }),
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
      setReference("");
      void qc.invalidateQueries({ queryKey: ["finance", "invoices"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  return (
    <Card>
      <CardBody className="space-y-3">
        <div>
          <Label htmlFor="manual-invoice">Invoice</Label>
          <Select
            id="manual-invoice"
            value={invoice}
            disabled={invoices.isLoading || (invoices.data?.length ?? 0) === 0}
            onChange={(e) => chooseInvoice(e.target.value, invoices.data ?? [])}
          >
            <option value="">
              {invoices.isLoading
                ? "Loading invoices…"
                : (invoices.data?.length ?? 0) === 0
                  ? "No invoices yet"
                  : "Choose an invoice"}
            </option>
            {(invoices.data ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {invoiceLabel(row)}
              </option>
            ))}
          </Select>
          {selected ? (
            <p className="mt-2 text-sm text-ink/70">
              Balance <Money amount={moneyAmount(selected.outstanding_amount)} />
            </p>
          ) : null}
        </div>
        {invoices.error ? (
          <p className="text-sm text-danger">
            {invoices.error instanceof Error
              ? invoices.error.message
              : "Failed to load invoices"}
          </p>
        ) : null}
        <div>
          <Label htmlFor="manual-amount">Amount</Label>
          <Input
            id="manual-amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            style={{ fontFamily: "var(--font-mono)" }}
          />
        </div>
        <div>
          <Label htmlFor="manual-method">Method</Label>
          <Select
            id="manual-method"
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="manual-reference">Reference</Label>
          <Input
            id="manual-reference"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="Receipt or teller number"
          />
        </div>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <Button
          disabled={save.isPending || !invoice || !amount}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Recording…" : "Record payment"}
        </Button>
      </CardBody>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Manual payment recorded."
      />
    </Card>
  );
}

export default function ManualPaymentPage() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader
        title="Manual payment"
        description="Record cash or bank transfer against an invoice"
      />
      <Suspense
        fallback={
          <Card>
            <CardBody>
              <p className="text-sm text-ink/70">Loading…</p>
            </CardBody>
          </Card>
        }
      >
        <ManualPaymentForm />
      </Suspense>
    </div>
  );
}
