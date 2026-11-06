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
