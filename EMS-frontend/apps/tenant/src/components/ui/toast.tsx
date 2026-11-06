"use client";

import { useEffect } from "react";
import { cn } from "@/lib/cn";

export type ToastProps = {
  open: boolean;
  message: string;
  onClose: () => void;
  durationMs?: number;
  className?: string;
};

/** Lightweight inline toast — no external toast library in the shell. */
export function Toast({
  open,
  message,
  onClose,
  durationMs = 2800,
  className,
}: ToastProps) {
  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(onClose, durationMs);
    return () => window.clearTimeout(id);
  }, [open, onClose, durationMs]);

  if (!open) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "fixed bottom-24 left-1/2 z-50 w-[min(100%-2rem,22rem)] -translate-x-1/2",
        "rounded-[var(--radius-nb)] border-[2.5px] border-ink bg-paper-card px-4 py-3 text-sm font-medium shadow-nb-lg lg:bottom-8",
        className,
      )}
    >
      {message}
    </div>
  );
}
