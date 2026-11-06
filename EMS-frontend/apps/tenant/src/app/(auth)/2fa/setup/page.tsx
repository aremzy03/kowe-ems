"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button, Input, Label } from "@/components/ui";
import {
  applyAuthSuccess,
  confirmEnroll2fa,
  enroll2fa,
  navigateAfterAuth,
} from "@/lib/api/auth";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-provider";
import { getPreAuthToken } from "@/lib/auth/token-store";

export default function TwoFaSetupPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [configUrl, setConfigUrl] = useState<string | null>(null);

  useEffect(() => {
    const preAuth = getPreAuthToken();
    if (!preAuth) {
      setError("No pending enrollment. Sign in again.");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await enroll2fa(preAuth);
        if (cancelled) return;
        setSecret(data.secret);
        setQrCode(data.qr_code);
        setConfigUrl(data.config_url);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiRequestError) {
          setError(mapDrfErrors(err.data).form ?? err.message);
        } else {
          setError(err instanceof Error ? err.message : "Enroll failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const totp = code.replace(/\D/g, "");
    if (totp.length !== 6) {
      setError("Enter the 6-digit confirmation code from your app.");
      return;
    }
    const preAuth = getPreAuthToken();
    if (!preAuth) {
      setError("No pending enrollment. Sign in again.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await confirmEnroll2fa(preAuth, totp);
      if (data.access && data.role) {
        applyAuthSuccess(data);
        setSession(data.access, data.role);
        navigateAfterAuth(data.role, router);
        return;
      }
      router.push("/2fa/verify");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Confirm failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <div className="rounded-[var(--radius-nb-lg)] border-[3.5px] border-ink bg-paper-card p-6 shadow-nb-lg sm:p-8">
        <p
          className="mb-1 text-sm text-accent-1"
          style={{ fontFamily: "var(--font-accent)" }}
        >
          School 2FA
        </p>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Set up 2FA
        </h1>
        <p className="mt-2 text-ink/75">
          Scan the QR with your authenticator, or enter the key manually. Required
          for admin and bursar accounts.
        </p>

        <div className="mt-6 flex flex-col items-center gap-4">
          {qrCode ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={
                qrCode.startsWith("data:")
                  ? qrCode
                  : `data:image/png;base64,${qrCode}`
              }
              alt="Authenticator QR code"
              className="h-44 w-44 rounded-[var(--radius-nb)] border-[3.5px] border-ink bg-paper shadow-nb"
            />
          ) : (
            <div
              className="flex h-44 w-44 items-center justify-center rounded-[var(--radius-nb)] border-[3.5px] border-ink bg-paper shadow-nb text-sm text-ink/60"
              aria-label="QR loading"
            >
              {error ? "—" : "Loading QR…"}
            </div>
          )}
          {secret ? (
            <p className="text-center text-sm text-ink/70">
              Manual key
              <br />
              <code
                className="mt-1 inline-block rounded-[var(--radius-nb-sm)] border-[1.5px] border-ink bg-paper px-2 py-1 text-sm font-bold shadow-nb-sm"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {secret}
              </code>
            </p>
          ) : null}
          {configUrl ? (
            <p className="break-all text-center text-xs text-ink/50">{configUrl}</p>
          ) : null}
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <Label htmlFor="confirm-code">Confirm code</Label>
            <Input
              id="confirm-code"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="123456"
              className="tracking-[0.3em]"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}
          <Button type="submit" className="w-full" size="lg" disabled={busy || !secret}>
            {busy ? "Confirming…" : "Confirm setup"}
          </Button>
        </form>

        <p className="mt-4">
          <Link href="/login" className="text-sm font-semibold text-ink underline">
            Back to login
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
