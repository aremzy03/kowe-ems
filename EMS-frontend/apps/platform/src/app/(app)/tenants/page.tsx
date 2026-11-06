"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Card,
  CardBody,
  EmptyState,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { fetchTenants } from "@/lib/api/platform";

function formatWhen(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function TenantsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["platform", "tenants"],
    queryFn: () => fetchTenants(),
  });

  const tenants = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Tenants"
        description="Schools on the platform. This screen does not provision a school."
      />

      {isLoading ? <p className="text-sm text-ink/70">Loading schools…</p> : null}
      {error ? (
        <p className="text-sm text-danger">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      ) : null}

      {data && tenants.length === 0 ? (
        <EmptyState
          headline="No schools yet"
          body="Schools appear here after a tenant is created."
        />
      ) : null}

      {data && tenants.length > 0 ? (
        <Card>
          <CardBody className="p-0">
            <Table className="border-0 shadow-none">
              <THead>
                <TR>
                  <TH>School</TH>
                  <TH>Schema</TH>
                  <TH>Slug</TH>
                  <TH>Primary domain</TH>
                  <TH>Status</TH>
                  <TH>Created</TH>
                </TR>
              </THead>
              <TBody>
                {tenants.map((row) => (
                  <TR key={row.id}>
                    <TD className="font-medium">{row.school_name}</TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {row.schema_name}
                    </TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>{row.slug}</TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {row.primary_domain ?? "—"}
                    </TD>
                    <TD>
                      <Badge variant={row.is_active ? "success" : "warning"}>
                        {row.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TD>
                    <TD className="whitespace-nowrap text-ink/80">
                      {formatWhen(row.created_at)}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
