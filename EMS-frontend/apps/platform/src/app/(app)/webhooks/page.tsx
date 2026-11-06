"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  type BadgeVariant,
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
import { fetchWebhookLogs } from "@/lib/api/platform";

const OUTCOME_LABEL: Record<string, string> = {
  applied: "Applied",
  error: "Error",
  signature_invalid: "Bad signature",
  invalid_json: "Invalid JSON",
  ignored_event: "Ignored",
  unknown_subaccount: "Unknown subaccount",
  missing_reference: "Missing reference",
};

function outcomeVariant(outcome: string): BadgeVariant {
  if (outcome === "applied") return "success";
  if (outcome === "error" || outcome === "signature_invalid") return "danger";
  if (outcome === "ignored_event") return "default";
  return "warning";
}

function formatWhen(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function detailText(errorMessage: string, payloadPreview: string) {
  const error = errorMessage.trim();
  if (error) return error;
  const preview = payloadPreview.trim();
  if (preview) return preview;
  return "—";
}

export default function WebhooksPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["platform", "webhooks"],
    queryFn: () => fetchWebhookLogs(),
  });

  const logs = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Webhooks"
        description="Recent Paystack deliveries recorded by the API. Replay stays on Django."
      />

      {isLoading ? <p className="text-sm text-ink/70">Loading deliveries…</p> : null}
      {error ? (
        <p className="text-sm text-danger">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      ) : null}

      {data && logs.length === 0 ? (
        <EmptyState
          headline="No deliveries yet"
          body="Rows appear after Paystack posts to the API."
        />
      ) : null}

      {data && logs.length > 0 ? (
        <Card>
          <CardBody className="p-0">
            <Table className="border-0 shadow-none">
              <THead>
                <TR>
                  <TH>Received</TH>
                  <TH>Outcome</TH>
                  <TH>Event</TH>
                  <TH>Reference</TH>
                  <TH>Subaccount</TH>
                  <TH>School</TH>
                  <TH>Signature</TH>
                  <TH>Error</TH>
                </TR>
              </THead>
              <TBody>
                {logs.map((row) => {
                  const detail = detailText(row.error_message, row.payload_preview);
                  return (
                    <TR key={row.id}>
                      <TD className="whitespace-nowrap text-ink/80">
                        {formatWhen(row.received_at)}
                      </TD>
                      <TD>
                        <Badge variant={outcomeVariant(row.outcome)}>
                          {OUTCOME_LABEL[row.outcome] ?? row.outcome}
                        </Badge>
                      </TD>
                      <TD style={{ fontFamily: "var(--font-mono)" }}>
                        {row.event || "—"}
                      </TD>
                      <TD style={{ fontFamily: "var(--font-mono)" }}>
                        {row.reference || "—"}
                      </TD>
                      <TD style={{ fontFamily: "var(--font-mono)" }}>
                        {row.subaccount_code || "—"}
                      </TD>
                      <TD>{row.school_name ?? "—"}</TD>
                      <TD>
                        <Badge variant={row.signature_valid ? "success" : "danger"}>
                          {row.signature_valid ? "Valid" : "Invalid"}
                        </Badge>
                      </TD>
                      <TD className="max-w-xs truncate" title={detail === "—" ? undefined : detail}>
                        {detail}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
