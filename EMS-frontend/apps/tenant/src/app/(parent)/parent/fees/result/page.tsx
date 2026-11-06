"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button, Card, CardBody, PageHeader } from "@/components/ui";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

function ResultPanel() {
  const searchParams = useSearchParams();
  const reference =
    searchParams.get("reference") ?? searchParams.get("trxref") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "failed">(
    reference ? "loading" : searchParams.get("status") === "failed" ? "failed" : "failed",
  );
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (!reference) {
      setMessage("Missing payment reference.");
      setStatus("failed");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        await financeApi.verifyPayment({ reference });
        if (!cancelled) {
          setStatus("success");
          setMessage("Payment verified with the school ledger.");
        }
      } catch (err) {
        if (cancelled) return;
        setStatus("failed");
        if (err instanceof ApiRequestError) {
          setMessage(mapDrfErrors(err.data).form ?? err.message);
        } else {
          setMessage(err instanceof Error ? err.message : "Verify failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reference]);

  const ok = status === "success";

  return (
    <Card>
      <CardBody className="space-y-4 text-center">
        <p
          className="text-2xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {status === "loading"
            ? "Verifying payment…"
            : ok
              ? "Payment successful"
              : "Payment failed"}
        </p>
        <p className="text-ink/75">{message}</p>
        {status !== "loading" ? (
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            <Link href="/parent/fees">
              <Button>Back to fees</Button>
            </Link>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

export default function ParentFeesResultPage() {
  return (
    <div className="mx-auto w-full max-w-md">
      <PageHeader
        title="Payment result"
        description="Verifies the Paystack reference with EMS-api"
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
        <ResultPanel />
      </Suspense>
    </div>
  );
}
