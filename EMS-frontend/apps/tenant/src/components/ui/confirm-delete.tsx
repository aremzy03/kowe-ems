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
};

export function ConfirmDeleteModal({
  open,
  onClose,
  onConfirm,
  title,
  description,
  pending = false,
  confirmLabel = "Delete",
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
    </Modal>
  );
}
