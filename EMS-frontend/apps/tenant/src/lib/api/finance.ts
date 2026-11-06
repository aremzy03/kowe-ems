import { apiFetch } from "@/lib/api/client";
import type { Paginated } from "@/lib/api/academics";

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

export type FeeStructure = {
  id: string;
  name: string;
  class_level: string;
  class_level_name?: string;
  term: string;
  term_name?: string;
  session_name?: string;
  amount: string;
};

export type InvoiceLineItem = {
  id: string;
  fee_structure?: string;
  name?: string;
  amount?: string;
};

export type Invoice = {
  id: string;
  student?: string;
  student_name?: string;
  admission_number?: string;
  term?: string;
  term_name?: string;
  session_name?: string;
  total_amount?: string;
  amount_paid?: string;
  outstanding_amount?: string;
  amount_due?: string;
  status?: string;
  reference?: string;
  line_items?: InvoiceLineItem[];
  created_at?: string;
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
  listInvoices: async (params?: { term?: string; class_level?: string }) => {
    const search = new URLSearchParams();
    if (params?.term) search.set("term", params.term);
    if (params?.class_level) search.set("class_level", params.class_level);
    const qs = search.toString();
    const data = await apiFetch<Paginated<Invoice> | Invoice[]>(
      `/api/finance/invoices/${qs ? `?${qs}` : ""}`,
      { auth: true },
    );
    return unwrapList(data);
  },
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
