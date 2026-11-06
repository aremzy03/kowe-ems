"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
  Money,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { fetchRevenue } from "@/lib/api/auth";

export default function PlatformRevenuePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["platform", "revenue"],
    queryFn: () => fetchRevenue(),
  });

  return (
    <div>
      <PageHeader
        title="Revenue"
        description="Cross-tenant commission from Paystack fee payments"
      />

      {isLoading ? <p className="text-sm text-ink/70">Loading revenue…</p> : null}
      {error ? (
        <p className="text-sm text-danger">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      ) : null}

      {data ? (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardBody className="space-y-1">
                <p className="text-sm font-medium text-ink/70">Gross volume</p>
                <p className="text-2xl font-bold">
                  <Money amount={Number(data.totals.gross_amount)} />
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="space-y-1">
                <p className="text-sm font-medium text-ink/70">Commission</p>
                <p className="text-2xl font-bold">
                  <Money amount={Number(data.totals.commission_amount)} />
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="space-y-1">
                <p className="text-sm font-medium text-ink/70">Net to schools</p>
                <p className="text-2xl font-bold">
                  <Money amount={Number(data.totals.net_to_school)} />
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="space-y-1">
                <p className="text-sm font-medium text-ink/70">Transactions</p>
                <p
                  className="text-2xl font-bold"
                  style={{ fontFamily: "var(--font-mono)" }}
                >
                  {data.totals.transaction_count}
                </p>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardBody className="p-0">
              <Table className="border-0 shadow-none">
                <THead>
                  <TR>
                    <TH>School</TH>
                    <TH>Schema</TH>
                    <TH>Gross</TH>
                    <TH>Commission</TH>
                    <TH>Net</TH>
                  </TR>
                </THead>
                <TBody>
                  {data.by_school.length === 0 ? (
                    <TR>
                      <TD colSpan={5} className="text-sm text-ink/65">
                        No revenue in this period.
                      </TD>
                    </TR>
                  ) : (
                    data.by_school.map((row, i) => (
                      <TR key={row.tenant_id ?? row.schema_name ?? i}>
                        <TD className="font-medium">
                          {row.school_name ?? row.name ?? "—"}
                        </TD>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.schema_name ?? "—"}
                        </TD>
                        <TD>
                          <Money amount={Number(row.gross_amount)} />
                        </TD>
                        <TD>
                          <Money amount={Number(row.commission_amount)} />
                        </TD>
                        <TD>
                          <Money amount={Number(row.net_to_school)} />
                        </TD>
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  );
}
