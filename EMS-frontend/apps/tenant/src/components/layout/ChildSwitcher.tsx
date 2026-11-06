"use client";

import { cn } from "@/lib/cn";
import { useParentChildren } from "@/lib/parent/children";

export function ChildSwitcher({ className }: { className?: string }) {
  const { children, selectedChildId, selectChild, isLoading } =
    useParentChildren();

  if (isLoading) {
    return (
      <p className={cn("text-sm text-ink/60", className)}>Loading children…</p>
    );
  }

  if (!children.length) {
    return (
      <p className={cn("text-sm text-ink/60", className)}>
        No linked students yet. Use Link student to redeem a code.
      </p>
    );
  }

  return (
    <div
      className={cn("flex gap-2 overflow-x-auto pb-1", className)}
      role="listbox"
      aria-label="Switch child"
    >
      {children.map((child) => {
        const selected = child.id === selectedChildId;
        return (
          <button
            key={child.id}
            type="button"
            role="option"
            aria-selected={selected}
            onClick={() => selectChild(child.id)}
            className={cn(
              "min-w-[9.5rem] shrink-0 rounded-[var(--radius-nb-sm)] border px-3 py-2 text-left",
              selected
                ? "border-ink bg-paper-tint font-bold text-ink"
                : "border-ink/20 bg-paper-card text-ink/75 hover:border-ink/40",
            )}
          >
            <span
              className="block truncate text-sm"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              {child.name}
            </span>
            <span
              className="mt-0.5 block text-xs text-ink/65"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {child.className || "—"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
