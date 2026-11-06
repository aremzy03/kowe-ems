/** Platform app: always uses PLATFORM_API_URL; never sends X-Tenant-Slug. */

export const PLATFORM_API_URL = (
  process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export const ROOT_DOMAIN = process.env.NEXT_PUBLIC_ROOT_DOMAIN ?? "localhost";
