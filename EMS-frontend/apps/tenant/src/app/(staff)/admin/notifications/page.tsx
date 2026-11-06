"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  type BadgeVariant,
  Button,
  Card,
  CardBody,
  EmptyState,
  Input,
  Label,
  PageHeader,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import {
  communicationsApi,
  type NotificationChannel,
  type NotificationLog,
  type NotificationStatus,
  type NotificationTrigger,
} from "@/lib/api/communications";
import { formatApiError } from "@/lib/api/errors";

const STATUS_LABEL: Record<NotificationStatus, string> = {
  queued: "Queued",
  sent: "Sent",
  failed: "Failed",
};

const CHANNEL_LABEL: Record<NotificationChannel, string> = {
  email: "Email",
  whatsapp: "WhatsApp",
};

const TRIGGER_LABEL: Record<NotificationTrigger, string> = {
  invoice_generated: "Invoice generated",
  payment_confirmed: "Payment confirmed",
  result_published: "Result published",
};

const RELATED_KIND: Record<NotificationTrigger, string> = {
  invoice_generated: "Invoice",
  payment_confirmed: "Payment",
  result_published: "Result",
};

function statusVariant(status: NotificationStatus): BadgeVariant {
  if (status === "sent") return "success";
  if (status === "failed") return "danger";
  return "warning";
}

function formatWhen(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function recipientParts(log: NotificationLog) {
  const name = log.recipient_name?.trim() || "";
  const email = log.recipient_email?.trim() || "";
  const primary = name || email || "—";
  const secondary = email && email !== primary ? email : "";
  return { primary, secondary };
}

function relatedLabel(log: NotificationLog) {
  const kind = RELATED_KIND[log.trigger_type] ?? "Related";
  const compact = log.related_object_id.replace(/-/g, "").slice(0, 8);
  return compact ? `${kind} ${compact}` : kind;
}

export default function AdminNotificationsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [triggerType, setTriggerType] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const dateRangeInvalid = Boolean(
    createdFrom && createdTo && createdTo < createdFrom,
  );
  const filtersActive = Boolean(
    status || channel || triggerType || createdFrom || createdTo,
  );

  const listParams = useMemo(() => {
    if (dateRangeInvalid) return null;
    return {
      ...(status ? { status: status as NotificationStatus } : {}),
      ...(channel ? { channel: channel as NotificationChannel } : {}),
      ...(triggerType
        ? { trigger_type: triggerType as NotificationTrigger }
        : {}),
      ...(createdFrom ? { created_from: createdFrom } : {}),
      ...(createdTo ? { created_to: createdTo } : {}),
    };
  }, [status, channel, triggerType, createdFrom, createdTo, dateRangeInvalid]);

  const logs = useQuery({
    queryKey: ["communications", "notifications", listParams],
    queryFn: () => communicationsApi.notifications.list(listParams ?? undefined),
    enabled: listParams !== null,
  });

  const resend = useMutation({
    mutationFn: (id: string) => communicationsApi.notifications.resend(id),
    onMutate: () => setPageError(null),
    onSuccess: (row) => {
      setToast(
        row.status === "queued"
          ? "Queued for resend. Delivery runs in the background."
          : `Resend finished with status ${STATUS_LABEL[row.status] ?? row.status}.`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["communications", "notifications"],
      });
    },
    onError: (err) => {
      setPageError(formatApiError(err, "Could not resend notification"));
    },
  });

  function clearFilters() {
    setStatus("");
    setChannel("");
    setTriggerType("");
    setCreatedFrom("");
    setCreatedTo("");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notification log"
        description="Email and WhatsApp deliveries for this school. Failed rows can be resent on the same log — this is not a broadcast composer."
      />

      {pageError ? <p className="text-sm text-danger">{pageError}</p> : null}

      <Card>
        <CardBody className="flex flex-wrap items-end gap-3">
          <div className="min-w-[9rem] flex-1">
            <Label htmlFor="notify-status">Status</Label>
            <Select
              id="notify-status"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="sent">Sent</option>
              <option value="failed">Failed</option>
            </Select>
          </div>
          <div className="min-w-[9rem] flex-1">
            <Label htmlFor="notify-channel">Channel</Label>
            <Select
              id="notify-channel"
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
            >
              <option value="">All channels</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
            </Select>
          </div>
          <div className="min-w-[11rem] flex-1">
            <Label htmlFor="notify-trigger">Trigger</Label>
            <Select
              id="notify-trigger"
              value={triggerType}
              onChange={(event) => setTriggerType(event.target.value)}
            >
              <option value="">All triggers</option>
              <option value="invoice_generated">Invoice generated</option>
              <option value="payment_confirmed">Payment confirmed</option>
              <option value="result_published">Result published</option>
            </Select>
          </div>
          <div className="min-w-[9rem] flex-1">
            <Label htmlFor="notify-from">From</Label>
            <Input
              id="notify-from"
              type="date"
              value={createdFrom}
              onChange={(event) => setCreatedFrom(event.target.value)}
            />
          </div>
          <div className="min-w-[9rem] flex-1">
            <Label htmlFor="notify-to">To</Label>
            <Input
              id="notify-to"
              type="date"
              value={createdTo}
              onChange={(event) => setCreatedTo(event.target.value)}
            />
          </div>
          {filtersActive ? (
            <button
              type="button"
              className="text-sm font-medium text-ink underline"
              onClick={clearFilters}
            >
              Clear filters
            </button>
          ) : null}
        </CardBody>
      </Card>

      {dateRangeInvalid ? (
        <p className="text-sm text-danger">
          “To” must be on or after “From”.
        </p>
      ) : null}

      <Card>
        <CardBody className="p-0">
          {dateRangeInvalid ? (
            <p className="p-4 text-sm text-ink/70">Fix the date range to load logs.</p>
          ) : logs.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading notifications…</p>
          ) : logs.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(logs.error, "Failed to load notifications")}
            </p>
          ) : (logs.data ?? []).length === 0 ? (
            <div className="p-4">
              <EmptyState
                headline={filtersActive ? "No notifications match" : "No notifications yet"}
                body={
                  filtersActive
                    ? "Try another status, channel, trigger, or date range."
                    : "Rows appear after invoices, payments, or published results are sent."
                }
                aside={
                  filtersActive
                    ? "Widen the filter, or wait for the next send."
                    : "Quiet until the next invoice, payment, or result goes out."
                }
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Created</TH>
                  <TH>Status</TH>
                  <TH>Channel</TH>
                  <TH>Trigger</TH>
                  <TH>Recipient</TH>
                  <TH>Related</TH>
                  <TH>Sent</TH>
                  <TH>Error</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(logs.data ?? []).map((log) => {
                  const error = log.error_message?.trim() || "";
                  const recipient = recipientParts(log);
                  const resending =
                    resend.isPending && resend.variables === log.id;
                  return (
                    <TR key={log.id}>
                      <TD className="whitespace-nowrap text-sm text-ink/80">
                        {formatWhen(log.created_at)}
                      </TD>
                      <TD>
                        <Badge variant={statusVariant(log.status)}>
                          {STATUS_LABEL[log.status] ?? log.status}
                        </Badge>
                      </TD>
                      <TD className="text-sm">
                        {CHANNEL_LABEL[log.channel] ?? log.channel}
                      </TD>
                      <TD className="text-sm">
                        {TRIGGER_LABEL[log.trigger_type] ?? log.trigger_type}
                      </TD>
                      <TD className="text-sm">
                        <div>{recipient.primary}</div>
                        {recipient.secondary ? (
                          <div className="text-xs text-ink/60">
                            {recipient.secondary}
                          </div>
                        ) : null}
                      </TD>
                      <TD
                        className="text-sm"
                        style={{ fontFamily: "var(--font-mono)" }}
                        title={log.related_object_id || undefined}
                      >
                        {relatedLabel(log)}
                      </TD>
                      <TD className="whitespace-nowrap text-sm text-ink/80">
                        {formatWhen(log.sent_at)}
                      </TD>
                      <TD
                        className="max-w-[14rem] truncate text-sm text-ink/70"
                        title={error || undefined}
                      >
                        {error || "—"}
                      </TD>
                      <TD>
                        {log.status === "failed" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={resend.isPending}
                            onClick={() => resend.mutate(log.id)}
                          >
                            {resending ? "Resending…" : "Resend"}
                          </Button>
                        ) : (
                          <span className="text-sm text-ink/45">—</span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Toast
        open={Boolean(toast)}
        onClose={() => setToast(null)}
        message={toast ?? ""}
      />
    </div>
  );
}
