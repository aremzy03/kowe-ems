import { apiFetch } from "@/lib/api/client";
import type { Paginated } from "@/lib/api/academics";

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

export type FeeStructure = {
  id: string;
  name: string;
  class_level: string | null;
  class_level_name?: string | null;
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

export type Payment = {
  id: string;
  invoice?: string;
  student?: string;
  student_name?: string;
  admission_number?: string;
  term?: string;
  term_name?: string;
  session_name?: string;
  amount: string;
  reference: string;
  status: string;
  gateway: string;
  method?: string | null;
  initiated_by?: string | null;
  initiated_by_email?: string | null;
  recorded_by?: string | null;
  recorded_by_email?: string | null;
  notes?: string;
  paid_at?: string | null;
  created_at?: string;
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
  payments?: Payment[];
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
      apiFetch<FeeStructure>("/api/finance/fee-structures/", {
        method: "POST",
        body,
        auth: true,
      }),
    update: (id: string, body: Partial<FeeStructure>) =>
      apiFetch<FeeStructure>(`/api/finance/fee-structures/${id}/`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    remove: (id: string) =>
      apiFetch(`/api/finance/fee-structures/${id}/`, {
        method: "DELETE",
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
  getInvoice: (id: string) =>
    apiFetch<Invoice>(`/api/finance/invoices/${id}/`, { auth: true }),
  listPayments: async (params?: {
    invoice?: string;
    status?: string;
    term?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.invoice) search.set("invoice", params.invoice);
    if (params?.status) search.set("status", params.status);
    if (params?.term) search.set("term", params.term);
    const qs = search.toString();
    const data = await apiFetch<Paginated<Payment> | Payment[]>(
      `/api/finance/payments/${qs ? `?${qs}` : ""}`,
      { auth: true },
    );
    return unwrapList(data);
  },
  getPayment: (id: string) =>
    apiFetch<Payment>(`/api/finance/payments/${id}/`, { auth: true }),
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
