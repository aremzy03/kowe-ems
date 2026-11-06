"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PaymentsTable } from "@/components/finance/PaymentsTable";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Money,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { financeApi } from "@/lib/api/finance";

function moneyAmount(value?: string): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function statusLabel(status?: string): string {
  if (status === "paid") return "Paid";
  if (status === "partially_paid") return "Partially paid";
  if (status === "unpaid") return "Unpaid";
  return status || "—";
}

function statusVariant(status?: string): "success" | "warning" | "info" {
  if (status === "paid") return "success";
  if (status === "partially_paid") return "warning";
  return "info";
}

function termLabel(session?: string, term?: string): string {
  return [session, term].filter(Boolean).join(" · ") || "—";
}

export default function BursarInvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const invoiceId = params.id;

  const invoice = useQuery({
    queryKey: ["finance", "invoice", invoiceId],
    queryFn: () => financeApi.getInvoice(invoiceId),
    enabled: Boolean(invoiceId),
  });

  const data = invoice.data;
  const balance = moneyAmount(data?.outstanding_amount);
  const payments = data?.payments ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={data?.student_name || "Invoice"}
        description={
          data
            ? [data.admission_number, termLabel(data.session_name, data.term_name)]
                .filter(Boolean)
                .join(" · ") || "Line items and payment history"
            : "Line items and payment history"
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/bursar/invoices"
              className="text-sm font-medium text-ink underline"
            >
              All invoices
            </Link>
            {data && balance > 0 ? (
              <Link
                href={`/bursar/payments/manual?invoice=${data.id}`}
                className="text-sm font-medium text-ink underline"
              >
                Record payment
              </Link>
            ) : null}
          </div>
        }
      />

      {invoice.isLoading ? (
        <p className="text-sm text-ink/70">Loading invoice…</p>
      ) : invoice.error ? (
        <p className="text-sm text-danger">
          {invoice.error instanceof Error
            ? invoice.error.message
            : "Failed to load invoice"}
        </p>
      ) : data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card>
              <CardBody>
                <p className="text-sm text-ink/70">Amount</p>
                <p className="mt-1 text-lg font-bold">
                  <Money amount={moneyAmount(data.total_amount)} />
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="text-sm text-ink/70">Paid</p>
                <p className="mt-1 text-lg font-bold">
                  <Money amount={moneyAmount(data.amount_paid)} />
                </p>
                <p className="mt-1 text-xs text-ink/60">
                  Successful payments only. Pending Paystack is not counted.
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-ink/70">Balance</p>
                  <p className="mt-1 text-lg font-bold">
                    <Money amount={balance} />
                  </p>
                </div>
                <Badge variant={statusVariant(data.status)}>
                  {statusLabel(data.status)}
                </Badge>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Line items</CardTitle>
            </CardHeader>
            <CardBody className="p-0">
              {(data.line_items ?? []).length === 0 ? (
                <p className="p-4 text-sm text-ink/70">No line items on this invoice.</p>
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Fee</TH>
                      <TH className="text-right">Amount</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {(data.line_items ?? []).map((item) => (
                      <TR key={item.id}>
                        <TD>{item.name || "Fee"}</TD>
                        <TD className="text-right">
                          <Money amount={moneyAmount(item.amount)} />
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>Payments</CardTitle>
              <Link
                href={`/bursar/payments?invoice=${data.id}`}
                className="text-sm font-medium text-ink underline"
              >
                Open in ledger
              </Link>
            </CardHeader>
            <CardBody className="p-0">
              <PaymentsTable
                payments={payments}
                emptyHeadline="No payments on this invoice"
                emptyBody="Record cash or a bank transfer, or wait for a parent Paystack checkout to appear here. Pending checkouts are not paid."
              />
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  );
}
