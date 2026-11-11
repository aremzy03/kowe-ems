"use client";

import { useState } from "react";
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

type SettlementAccount = {
  bank_code?: string;
  bank_name?: string;
  account_number?: string;
  account_name?: string;
  subaccount_code?: string;
  is_verified?: boolean;
  is_active?: boolean;
};

type PaymentAccountResponse = {
  onboarded?: boolean;
  detail?: string;
  account?: SettlementAccount;
};

export function PaymentAccountPanel() {
  const queryClient = useQueryClient();
  const [bankCode, setBankCode] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["finance", "payment-account"],
    queryFn: () => financeApi.paymentAccount.get() as Promise<PaymentAccountResponse>,
  });

  const save = useMutation({
    mutationFn: () =>
      financeApi.paymentAccount.save({
        bank_code: bankCode.trim(),
        account_number: accountNumber.trim(),
      }),
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
      setBankCode("");
      setAccountNumber("");
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

  const account = query.data?.onboarded ? query.data.account : undefined;
  const configured = Boolean(account?.subaccount_code || account?.is_verified);

  return (
    <div className="mx-auto w-full max-w-lg">
      <PageHeader
        title="Payment account"
        description="School settlement account for online fee collection"
        actions={
          configured ? (
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
          {query.isError ? (
            <p className="text-sm text-danger">Could not load the payment account.</p>
          ) : null}

          {configured && account ? (
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-ink/70">Account name</dt>
                <dd className="font-semibold">{account.account_name}</dd>
              </div>
              <div>
                <dt className="text-ink/70">Bank</dt>
                <dd>{account.bank_name}</dd>
              </div>
              <div>
                <dt className="text-ink/70">Account number</dt>
                <dd style={{ fontFamily: "var(--font-mono)" }}>
                  {account.account_number}
                </dd>
              </div>
              <div>
                <dt className="text-ink/70">Bank code</dt>
                <dd style={{ fontFamily: "var(--font-mono)" }}>{account.bank_code}</dd>
              </div>
              <p className="text-ink/70">
                Online payments settle to this account. Replacing it is not
                available here.
              </p>
            </dl>
          ) : (
            <>
              <p className="text-sm text-ink/70">
                Verify the school bank account with Paystack. Parents cannot pay
                online until this is saved.
              </p>
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
                  inputMode="numeric"
                  style={{ fontFamily: "var(--font-mono)" }}
                />
              </div>
              {error ? <p className="text-sm text-danger">{error}</p> : null}
              <Button
                onClick={() => save.mutate()}
                disabled={
                  save.isPending || !bankCode.trim() || !accountNumber.trim()
                }
              >
                {save.isPending ? "Saving…" : "Save payment account"}
              </Button>
            </>
          )}
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
