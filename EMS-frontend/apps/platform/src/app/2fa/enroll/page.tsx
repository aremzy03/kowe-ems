import { redirect } from "next/navigation";

/** Alias for setup — keep /2fa/enroll available to match the tenant auth flow. */
export default function TwoFaEnrollPage() {
  redirect("/2fa/setup");
}
