import { ApiRequestError } from "@/lib/api/client";

/**
 * Map DRF validation errors / detail strings onto form fields.
 */
export function mapDrfErrors(
  data: unknown,
): { form?: string; fields: Record<string, string> } {
  const fields: Record<string, string> = {};
  if (!data || typeof data !== "object") {
    return { form: "Request failed", fields };
  }
  const obj = data as Record<string, unknown>;
  if (typeof obj.detail === "string") {
    return { form: obj.detail, fields };
  }
  if (Array.isArray(obj.non_field_errors)) {
    return { form: String(obj.non_field_errors[0]), fields };
  }
  for (const [key, value] of Object.entries(obj)) {
    if (key === "detail") continue;
    if (Array.isArray(value) && value.length) {
      fields[key] = String(value[0]);
    } else if (typeof value === "string") {
      fields[key] = value;
    }
  }
  return { fields };
}

function fieldSummary(data: unknown): string {
  const mapped = mapDrfErrors(data);
  if (mapped.form && mapped.form !== "Request failed") return mapped.form;
  const lines = Object.entries(mapped.fields)
    .filter(([, value]) => value && !value.includes("[object Object]"))
    .map(([key, value]) => (/^\d+$/.test(key) ? value : `${key}: ${value}`));
  if (lines.length) return lines.join("; ");
  return mapped.form ?? "";
}

function bulkEntryMessages(data: unknown): string[] {
  if (!data || typeof data !== "object" || Array.isArray(data)) return [];
  const results = (data as { results?: unknown }).results;
  if (!Array.isArray(results)) return [];
  const lines: string[] = [];
  for (const row of results) {
    if (!row || typeof row !== "object") continue;
    const record = row as { success?: boolean; errors?: unknown };
    if (record.success !== false) continue;
    const text = fieldSummary(record.errors);
    if (text) lines.push(text);
    if (lines.length >= 3) break;
  }
  return lines;
}

/** DRF body or per-entry bulk-upsert failures, via mapDrfErrors. */
export function formatApiError(err: unknown, fallback: string): string {
  if (!(err instanceof ApiRequestError)) {
    return err instanceof Error ? err.message : fallback;
  }
  const summary = fieldSummary(err.data);
  const bulk = bulkEntryMessages(err.data);
  if (summary && bulk.length) return `${summary}. ${bulk.join("; ")}`;
  if (summary) return summary;
  if (bulk.length) {
    const failed = (err.data as { failed?: unknown }).failed;
    const prefix =
      typeof failed === "number" && failed > 0
        ? `${failed} ${failed === 1 ? "entry" : "entries"} failed. `
        : "";
    return `${prefix}${bulk.join("; ")}`;
  }
  return err.message || fallback;
}

/** 207 bulk responses are HTTP-ok; surface the failed entries. */
export function partialBulkFailureMessage(data: unknown): string | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const failed = (data as { failed?: unknown }).failed;
  if (typeof failed !== "number" || failed <= 0) return null;
  const bulk = bulkEntryMessages(data);
  const noun = failed === 1 ? "entry" : "entries";
  return bulk.length
    ? `${failed} ${noun} failed. ${bulk.join("; ")}`
    : `${failed} ${noun} failed.`;
}
