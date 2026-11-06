"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardBody,
  Input,
  Label,
  PageHeader,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type PaymentAccount = {
  bank_code?: string;
  bank_name?: string;
  account_number?: string;
  account_name?: string;
  subaccount_code?: string;
  verified?: boolean;
};

export default function BursarPaymentAccountPage() {
  const queryClient = useQueryClient();
  const [bankCode, setBankCode] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["finance", "payment-account"],
    queryFn: () => financeApi.paymentAccount.get() as Promise<PaymentAccount>,
  });

  useEffect(() => {
    if (query.data) {
      setBankCode(query.data.bank_code ?? "");
      setAccountNumber(query.data.account_number ?? "");
    }
  }, [query.data]);

  const save = useMutation({
    mutationFn: () =>
      financeApi.paymentAccount.save({
        bank_code: bankCode,
        account_number: accountNumber,
      }),
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
      void queryClient.invalidateQueries({
        queryKey: ["finance", "payment-account"],
      });
    },
    onError: (err) => {
      if (err instanceof ApiRequestError) {
        setError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    },
  });

  const account = query.data;

  return (
    <div className="mx-auto w-full max-w-lg">
      <PageHeader
        title="Payment account"
        description="School settlement account for fee collections"
        actions={
          account?.verified || account?.subaccount_code ? (
            <Badge variant="success">Configured</Badge>
          ) : (
            <Badge variant="warning">Not set</Badge>
          )
        }
      />

      <Card>
        <CardBody className="space-y-4">
          {query.isLoading ? (
            <p className="text-sm text-ink/70">Loading…</p>
          ) : null}
          {account?.account_name ? (
            <p className="text-sm text-ink/70">
              Account name: <strong>{account.account_name}</strong>
            </p>
          ) : null}
          {account?.bank_name ? (
            <p className="text-sm text-ink/70">Bank: {account.bank_name}</p>
          ) : null}
          <div className="space-y-1.5">
            <Label htmlFor="pa-bank-code">Bank code</Label>
            <Input
              id="pa-bank-code"
              value={bankCode}
              onChange={(e) => setBankCode(e.target.value)}
              placeholder="057"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pa-number">Account number</Label>
            <Input
              id="pa-number"
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            onClick={() => save.mutate()}
            disabled={save.isPending}
          >
            {save.isPending ? "Saving…" : "Save payment account"}
          </Button>
        </CardBody>
      </Card>

      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Payment account saved."
      />
    </div>
  );
}
