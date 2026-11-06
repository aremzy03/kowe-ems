import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { KoweLockup } from "./KoweLockup";

type AuthShellProps = {
  children: ReactNode;
  className?: string;
};

/** Dial-up Paper Brutalism chrome for auth flows — horizontal lockup as brand hero. */
export function AuthShell({ children, className }: AuthShellProps) {
  return (
    <main
      className={cn(
        "relative flex min-h-screen items-center justify-center px-4 py-12 text-ink",
        className,
      )}
    >
      <div className="relative z-10 w-full max-w-lg">
        <div className="mb-8 flex justify-center">
          <KoweLockup width={220} />
        </div>
        {children}
      </div>
    </main>
  );
}
