"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Suspense,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui";
import {
  applyAuthSuccess,
  navigateAfterAuth,
  verify2fa,
} from "@/lib/api/auth";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-provider";
import { getPreAuthToken, getRole } from "@/lib/auth/token-store";

function TwoFaVerifyForm() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [digits, setDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);
  const role = getRole();

  function updateDigit(index: number, value: string) {
    const cleaned = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = cleaned;
    setDigits(next);
    if (cleaned && index < 5) {
      inputsRef.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const code = digits.join("");
    if (code.length !== 6) {
      setError("Enter the 6-digit code from your authenticator app.");
      return;
    }
    const preAuth = getPreAuthToken();
    if (!preAuth) {
      setError("No pending 2FA session. Sign in again.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await verify2fa(preAuth, code);
      if (data.access && data.role) {
        applyAuthSuccess(data);
        setSession(data.access, data.role, data.me);
        navigateAfterAuth(data.role, router);
        return;
      }
      setError("Unexpected response from verify.");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Verification failed");
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
          Verify 2FA
        </h1>
        <p className="mt-2 text-ink/75">
          Enter the 6-digit code
          {role ? (
            <>
              {" "}
              for <span className="font-semibold text-ink">{role}</span>
            </>
          ) : null}{" "}
          access.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <div className="flex justify-between gap-2">
            {digits.map((digit, index) => (
              <input
                key={index}
                ref={(el) => {
                  inputsRef.current[index] = el;
                }}
                inputMode="numeric"
                autoComplete={index === 0 ? "one-time-code" : "off"}
                maxLength={1}
                value={digit}
                onChange={(e) => updateDigit(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(index, e)}
                aria-label={`Digit ${index + 1}`}
                className="h-12 w-10 rounded-[var(--radius-nb)] border-[2.5px] border-ink bg-paper text-center text-lg font-bold shadow-nb-sm focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-accent-1 sm:h-14 sm:w-12"
                style={{ fontFamily: "var(--font-mono)" }}
              />
            ))}
          </div>
          {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}
          <Button type="submit" className="w-full" size="lg" disabled={busy}>
            {busy ? "Verifying…" : "Verify"}
          </Button>
        </form>

        <p className="mt-5 text-sm text-ink/65">
          First time?{" "}
          <Link href="/2fa/setup" className="font-semibold text-accent-1 underline">
            Set up authenticator
          </Link>
        </p>
        <p className="mt-3">
          <Link href="/login" className="text-sm font-semibold text-ink underline">
            Back to login
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}

export default function TwoFaVerifyPage() {
  return (
    <Suspense
      fallback={
        <AuthShell>
          <p className="text-center text-ink/70">Loading verification…</p>
        </AuthShell>
      }
    >
      <TwoFaVerifyForm />
    </Suspense>
  );
}
