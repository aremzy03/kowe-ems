import { NextResponse, type NextRequest } from "next/server";
import { EMS_TENANT_SLUG_HEADER } from "@/lib/api/config";
import { getTenantSlug } from "@/lib/api/tenant";

/**
 * Tenant-context only: Host → x-ems-tenant-slug for RSC/server apiFetch.
 * Auth route guards live in client RoleGuard (prompt 03) — not here.
 * Does not read refresh_token (API-host cookie). Does not rewrite API hosts.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const requestHeaders = new Headers(request.headers);
  const slug = getTenantSlug(request.headers.get("host") ?? "");
  if (slug) {
    requestHeaders.set(EMS_TENANT_SLUG_HEADER, slug);
  }

  return NextResponse.next({
    request: { headers: requestHeaders },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|.*\\..*).*)"],
};
