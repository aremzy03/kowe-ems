"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";
import { Button } from "./button";

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
};

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  className,
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className={cn(
        "fixed inset-0 m-auto max-h-[90vh] w-[min(100%-2rem,28rem)] overflow-auto",
        "rounded-[var(--radius-nb-lg)] border-[3.5px] border-ink bg-paper-card p-0 shadow-nb-xl",
        "backdrop:bg-ink/50",
        "open:flex open:flex-col",
        className,
      )}
      onClose={handleClose}
      onClick={(e) => {
        if (e.target === dialogRef.current) handleClose();
      }}
    >
      <div className="flex items-start justify-between gap-3 border-b-[2.5px] border-ink p-4">
        <h2
          id={titleId}
          className="text-xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          {title}
        </h2>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Close dialog"
          onClick={handleClose}
          className="shrink-0"
        >
          ✕
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-4">{children}</div>
      {footer ? (
        <div className="flex flex-wrap justify-end gap-2 border-t-[2.5px] border-ink p-4">
          {footer}
        </div>
      ) : null}
    </dialog>
  );
}

/** Alias for teams expecting Dialog naming */
export const Dialog = Modal;
