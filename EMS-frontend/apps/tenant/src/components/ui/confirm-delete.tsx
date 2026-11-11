"use client";

import { Button } from "./button";
import { Modal } from "./modal";

export type ConfirmDeleteModalProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: string;
  pending?: boolean;
  confirmLabel?: string;
  error?: string | null;
};

export function ConfirmDeleteModal({
  open,
  onClose,
  onConfirm,
  title,
  description,
  pending = false,
  confirmLabel = "Delete",
  error = null,
}: ConfirmDeleteModalProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? "Deleting…" : confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-ink/80">{description}</p>
      {error ? (
        <p role="alert" className="mt-3 text-sm font-medium" style={{ color: "#8B2424" }}>
          {error}
        </p>
      ) : null}
    </Modal>
  );
}
