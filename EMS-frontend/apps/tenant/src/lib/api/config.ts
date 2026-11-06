/**
 * Fixed API bases — never interpolate a school slug into these URLs.
 * Tenant selection is X-Tenant-Slug on the request, not Host on the API.
 */

export const TENANT_API_URL = (
  process.env.NEXT_PUBLIC_TENANT_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export const PLATFORM_API_URL = (
  process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? TENANT_API_URL
).replace(/\/$/, "");

export const ROOT_DOMAIN = process.env.NEXT_PUBLIC_ROOT_DOMAIN ?? "localhost";

/** Hostname where platform UI runs; getTenantSlug returns null for this host. */
export const PLATFORM_HOST =
  process.env.NEXT_PUBLIC_PLATFORM_HOST ?? "platform.localhost";

/** Absolute origin for the platform workspace app (landing links). */
export const PLATFORM_ORIGIN =
  process.env.NEXT_PUBLIC_PLATFORM_ORIGIN ??
  `http://${PLATFORM_HOST}:3001`;

export const EMS_TENANT_SLUG_HEADER = "x-ems-tenant-slug";
