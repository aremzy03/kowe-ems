import { Badge, type BadgeVariant } from "@/components/ui";
import type { AttendanceStatus } from "@/lib/api/attendance";

const STATUS_META: Record<
  AttendanceStatus,
  { label: string; variant: BadgeVariant }
> = {
  present: { label: "Present", variant: "success" },
  absent: { label: "Absent", variant: "danger" },
  late: { label: "Late", variant: "warning" },
  excused: { label: "Excused", variant: "info" },
};

export function AttendanceStatusBadge({
  status,
}: {
  status: string | null | undefined;
}) {
  const key = status as AttendanceStatus;
  const meta = STATUS_META[key];
  if (!meta) {
    return <Badge variant="default">{status || "Unknown"}</Badge>;
  }
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}

/** Mark-entry status for admin overview (date mode). */
export function MarkEntryStatusBadge({
  status,
}: {
  status: string | null | undefined;
}) {
  const map: Record<string, { label: string; variant: BadgeVariant }> = {
    complete: { label: "Complete", variant: "success" },
    partial: { label: "Partial", variant: "warning" },
    pending: { label: "Pending", variant: "danger" },
    empty: { label: "Empty", variant: "default" },
  };
  const meta = status ? map[status] : undefined;
  if (!meta) {
    return <Badge variant="default">{status || "—"}</Badge>;
  }
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
