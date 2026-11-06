import { redirect } from "next/navigation";

/** Legacy shell path — emails use /accept-invite?token= */
export default async function InviteAcceptRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const token = params.token;
  const qs = new URLSearchParams();
  if (typeof token === "string") qs.set("token", token);
  const suffix = qs.toString() ? `?${qs}` : "";
  redirect(`/accept-invite${suffix}`);
}
