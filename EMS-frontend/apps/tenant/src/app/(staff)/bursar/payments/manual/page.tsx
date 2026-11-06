"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Input,
  Label,
  PageHeader,
  Select,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function ManualPaymentPage() {
  const [invoice, setInvoice] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      financeApi.manualPayment({
        invoice,
        amount,
        method,
        reference,
      }),
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
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
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader
        title="Manual payment"
        description="Record cash or bank transfer against an invoice"
      />
      <Card>
        <CardBody className="space-y-3">
          <div>
            <Label>Invoice id</Label>
            <Input
              value={invoice}
              onChange={(e) => setInvoice(e.target.value)}
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div>
            <Label>Amount</Label>
            <Input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div>
            <Label>Method</Label>
            <Select value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank transfer</option>
            </Select>
          </div>
          <div>
            <Label>Reference</Label>
            <Input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
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
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Manual payment recorded."
      />
    </div>
  );
}
