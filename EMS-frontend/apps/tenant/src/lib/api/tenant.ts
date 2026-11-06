import { PLATFORM_HOST, ROOT_DOMAIN } from "@/lib/api/config";

/**
 * Derive school slug from the frontend hostname.
 * `{slug}.{ROOT_DOMAIN}` → slug (lowercase).
 * Returns null for ROOT_DOMAIN itself, PLATFORM_HOST, or unparseable hosts.
 */
export function getTenantSlug(hostname?: string): string | null {
  const host = (hostname ?? (typeof window !== "undefined" ? window.location.hostname : ""))
    .toLowerCase()
    .split(":")[0]
    .trim();

  if (!host) return null;

  const root = ROOT_DOMAIN.toLowerCase();
  const platform = PLATFORM_HOST.toLowerCase().split(":")[0];

  if (host === root || host === platform) return null;
  if (host === "127.0.0.1" || host === "0.0.0.0") return null;

  const suffix = `.${root}`;
  if (!host.endsWith(suffix)) return null;

  const label = host.slice(0, -suffix.length);
  if (!label || label.includes(".")) return null;

  return label;
}
