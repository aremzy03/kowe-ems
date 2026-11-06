import { apiFetch } from "@/lib/api/client";
import type { Paginated } from "@/lib/api/academics";

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

export type FeeStructure = {
  id: string;
  name: string;
  class_level?: string;
  term?: string;
  amount?: string;
  items?: unknown[];
};

export type Invoice = {
  id: string;
  student?: string;
  amount_due?: string;
  amount_paid?: string;
  status?: string;
  reference?: string;
};

export const financeApi = {
  feeStructures: {
    list: async () => {
      const data = await apiFetch<Paginated<FeeStructure> | FeeStructure[]>(
        "/api/finance/fee-structures/",
        { auth: true },
      );
      return unwrapList(data);
    },
    create: (body: unknown) =>
      apiFetch("/api/finance/fee-structures/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  paymentAccount: {
    get: () => apiFetch("/api/finance/payment-account/", { auth: true }),
    save: (body: unknown) =>
      apiFetch("/api/finance/payment-account/", {
        method: "POST",
        body,
        auth: true,
      }),
  },
  generateInvoices: (body: unknown) =>
    apiFetch("/api/finance/invoices/generate/", {
      method: "POST",
      body,
      auth: true,
    }),
  myInvoices: async () => {
    const data = await apiFetch<Paginated<Invoice> | Invoice[]>(
      "/api/finance/my-invoices/",
      { auth: true },
    );
    return unwrapList(data);
  },
  initializePayment: (body: unknown) =>
    apiFetch<{ authorization_url?: string; reference?: string }>(
      "/api/finance/payments/initialize/",
      { method: "POST", body, auth: true },
    ),
  verifyPayment: (body: unknown) =>
    apiFetch("/api/finance/payments/verify/", {
      method: "POST",
      body,
      auth: true,
    }),
  manualPayment: (body: unknown) =>
    apiFetch("/api/finance/payments/manual/", {
      method: "POST",
      body,
      auth: true,
    }),
  collectionsDashboard: (term: string) =>
    apiFetch(
      `/api/finance/dashboard/collections/?term=${encodeURIComponent(term)}`,
      { auth: true },
    ),
};
