import Link from "next/link";
import {
  Badge,
  EmptyState,
  Money,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import type { Payment } from "@/lib/api/finance";

function moneyAmount(value?: string | null): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatWhen(iso?: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function methodLabel(payment: Payment): string {
  if (payment.gateway === "manual") {
    if (payment.method === "bank_transfer") return "Bank transfer";
    if (payment.method === "cash") return "Cash";
    return "Manual";
  }
  if (payment.gateway === "paystack") return "Paystack";
  return payment.gateway || "—";
}

function paymentStatusLabel(status?: string): string {
  if (status === "success") return "Success";
  if (status === "pending") return "Pending";
  if (status === "failed") return "Failed";
  return status || "—";
}

function paymentStatusVariant(
  status?: string,
): "success" | "warning" | "danger" | "info" {
  if (status === "success") return "success";
  if (status === "pending") return "warning";
  if (status === "failed") return "danger";
  return "info";
}

export type PaymentsTableProps = {
  payments: Payment[];
  /** Ledger shows student + invoice link; invoice detail hides those columns. */
  showStudent?: boolean;
  emptyHeadline?: string;
  emptyBody?: string;
};

export function PaymentsTable({
  payments,
  showStudent = false,
  emptyHeadline = "No payments yet",
  emptyBody = "Recorded cash, transfers, and Paystack checkouts will show here.",
}: PaymentsTableProps) {
  if (payments.length === 0) {
    return (
      <div className="p-4">
        <EmptyState headline={emptyHeadline} body={emptyBody} />
      </div>
    );
  }

  return (
    <Table>
      <THead>
        <TR>
          <TH>Date</TH>
          {showStudent ? <TH>Student</TH> : null}
          <TH className="text-right">Amount</TH>
          <TH>Method</TH>
          <TH>Reference</TH>
          <TH>Status</TH>
          {showStudent ? <TH /> : null}
        </TR>
      </THead>
      <TBody>
        {payments.map((payment) => (
          <TR key={payment.id}>
            <TD>{formatWhen(payment.paid_at || payment.created_at)}</TD>
            {showStudent ? (
              <TD>
                <div>{payment.student_name || "Student"}</div>
                {payment.admission_number ? (
                  <div
                    className="text-xs text-ink/70"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {payment.admission_number}
                  </div>
                ) : null}
              </TD>
            ) : null}
            <TD className="text-right">
              <Money amount={moneyAmount(payment.amount)} />
            </TD>
            <TD>{methodLabel(payment)}</TD>
            <TD>
              <span style={{ fontFamily: "var(--font-mono)" }} className="text-xs">
                {payment.reference}
              </span>
            </TD>
            <TD>
              <Badge variant={paymentStatusVariant(payment.status)}>
                {paymentStatusLabel(payment.status)}
              </Badge>
            </TD>
            {showStudent && payment.invoice ? (
              <TD className="text-right">
                <Link
                  href={`/bursar/invoices/${payment.invoice}`}
                  className="text-sm font-medium text-ink underline"
                >
                  Invoice
                </Link>
              </TD>
            ) : showStudent ? (
              <TD />
            ) : null}
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
