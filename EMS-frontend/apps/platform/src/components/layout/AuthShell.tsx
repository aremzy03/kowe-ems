import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type AuthShellProps = {
  children: ReactNode;
  className?: string;
};

/** Dial-up Paper Brutalism chrome for auth flows */
export function AuthShell({ children, className }: AuthShellProps) {
  return (
    <main
      className={cn(
        "relative flex min-h-screen items-center justify-center bg-paper px-4 py-12 text-ink",
        className,
      )}
      style={{
        backgroundImage:
          "radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--color-ink) 8%, transparent) 1px, transparent 0)",
        backgroundSize: "12px 12px",
      }}
    >
      <div className="relative z-10 w-full max-w-lg">{children}</div>
    </main>
  );
}
