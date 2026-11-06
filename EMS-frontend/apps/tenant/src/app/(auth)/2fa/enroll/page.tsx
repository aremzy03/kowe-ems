import { redirect } from "next/navigation";

/** Alias for setup — keep /2fa/enroll available per auth prompt */
export default function TwoFaEnrollPage() {
  redirect("/2fa/setup");
}
