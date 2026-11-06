export type PaymentMethod = "Cash" | "Transfer" | "Paystack";

export type PaymentStatus = "Paid" | "Partial" | "Pending" | "Overdue";

export type FeeLineItem = {
  id: string;
  label: string;
  amount: number;
};

export type FeeStructure = {
  id: string;
  name: string;
  className: string;
  term: string;
  lineItems: FeeLineItem[];
  updatedAt: string;
};

export type InvoicePayment = {
  id: string;
  date: string;
  amount: number;
  method: PaymentMethod;
  reference: string;
};

export type Invoice = {
  id: string;
  number: string;
  studentName: string;
  studentId: string;
  className: string;
  term: string;
  status: PaymentStatus;
  dueDate: string;
  lineItems: FeeLineItem[];
  payments: InvoicePayment[];
};

export type RecentPayment = {
  id: string;
  date: string;
  studentName: string;
  invoiceNumber: string;
  amount: number;
  method: PaymentMethod;
  reference: string;
};

export type PaymentAccount = {
  bankName: string;
  accountName: string;
  accountNumberMasked: string;
  accountNumberFull: string;
  verified: boolean;
};

export const BURSAR_COLLECTIONS = {
  collectedThisTerm: 18_450_000,
  outstanding: 4_280_500,
  overdueCount: 37,
  paidToday: 620_000,
};

export const BURSAR_RECENT_PAYMENTS: RecentPayment[] = [
  {
    id: "pay_r1",
    date: "2026-03-04",
    studentName: "Adaeze Okeke",
    invoiceNumber: "INV-2026-0142",
    amount: 85_000,
    method: "Paystack",
    reference: "PSK-9F2A1C",
  },
  {
    id: "pay_r2",
    date: "2026-03-04",
    studentName: "Tunde Balogun",
    invoiceNumber: "INV-2026-0088",
    amount: 120_000,
    method: "Transfer",
    reference: "TRF-884201",
  },
  {
    id: "pay_r3",
    date: "2026-03-03",
    studentName: "Chioma Eze",
    invoiceNumber: "INV-2026-0110",
    amount: 45_000,
    method: "Cash",
    reference: "CASH-0312",
  },
  {
    id: "pay_r4",
    date: "2026-03-03",
    studentName: "Ibrahim Musa",
    invoiceNumber: "INV-2026-0061",
    amount: 200_000,
    method: "Paystack",
    reference: "PSK-7B31DE",
  },
  {
    id: "pay_r5",
    date: "2026-03-02",
    studentName: "Ngozi Okafor",
    invoiceNumber: "INV-2026-0034",
    amount: 95_000,
    method: "Transfer",
    reference: "TRF-771903",
  },
];

export const BURSAR_FEE_STRUCTURES: FeeStructure[] = [
  {
    id: "fs_01",
    name: "JSS 1 — First Term",
    className: "JSS 1",
    term: "2025/2026 · First Term",
    updatedAt: "2026-01-12",
    lineItems: [
      { id: "li_1", label: "Tuition", amount: 120_000 },
      { id: "li_2", label: "Development levy", amount: 25_000 },
      { id: "li_3", label: "ICT fee", amount: 15_000 },
      { id: "li_4", label: "PTA", amount: 5_000 },
    ],
  },
  {
    id: "fs_02",
    name: "SSS 2 — First Term",
    className: "SSS 2",
    term: "2025/2026 · First Term",
    updatedAt: "2026-01-14",
    lineItems: [
      { id: "li_5", label: "Tuition", amount: 180_000 },
      { id: "li_6", label: "Lab fee", amount: 30_000 },
      { id: "li_7", label: "Exam fee", amount: 20_000 },
      { id: "li_8", label: "PTA", amount: 5_000 },
    ],
  },
  {
    id: "fs_03",
    name: "Primary 5 — First Term",
    className: "Primary 5",
    term: "2025/2026 · First Term",
    updatedAt: "2026-01-10",
    lineItems: [
      { id: "li_9", label: "Tuition", amount: 90_000 },
      { id: "li_10", label: "Books & materials", amount: 35_000 },
      { id: "li_11", label: "Sports", amount: 8_000 },
    ],
  },
];

export function feeStructureTotal(structure: FeeStructure): number {
  return structure.lineItems.reduce((sum, item) => sum + item.amount, 0);
}

export const BURSAR_INVOICES: Invoice[] = [
  {
    id: "inv_01",
    number: "INV-2026-0142",
    studentName: "Adaeze Okeke",
    studentId: "TA-2025-0142",
    className: "JSS 1A",
    term: "2025/2026 · First Term",
    status: "Partial",
    dueDate: "2026-02-28",
    lineItems: [
      { id: "ili_1", label: "Tuition", amount: 120_000 },
      { id: "ili_2", label: "Development levy", amount: 25_000 },
      { id: "ili_3", label: "ICT fee", amount: 15_000 },
      { id: "ili_4", label: "PTA", amount: 5_000 },
    ],
    payments: [
      {
        id: "ip_1",
        date: "2026-03-04",
        amount: 85_000,
        method: "Paystack",
        reference: "PSK-9F2A1C",
      },
    ],
  },
  {
    id: "inv_02",
    number: "INV-2026-0088",
    studentName: "Tunde Balogun",
    studentId: "TA-2024-0088",
    className: "SSS 2B",
    term: "2025/2026 · First Term",
    status: "Paid",
    dueDate: "2026-02-28",
    lineItems: [
      { id: "ili_5", label: "Tuition", amount: 180_000 },
      { id: "ili_6", label: "Lab fee", amount: 30_000 },
      { id: "ili_7", label: "Exam fee", amount: 20_000 },
      { id: "ili_8", label: "PTA", amount: 5_000 },
    ],
    payments: [
      {
        id: "ip_2",
        date: "2026-03-04",
        amount: 235_000,
        method: "Transfer",
        reference: "TRF-884201",
      },
    ],
  },
  {
    id: "inv_03",
    number: "INV-2026-0110",
    studentName: "Chioma Eze",
    studentId: "TA-2025-0110",
    className: "JSS 2A",
    term: "2025/2026 · First Term",
    status: "Overdue",
    dueDate: "2026-02-15",
    lineItems: [
      { id: "ili_9", label: "Tuition", amount: 130_000 },
      { id: "ili_10", label: "ICT fee", amount: 15_000 },
      { id: "ili_11", label: "PTA", amount: 5_000 },
    ],
    payments: [
      {
        id: "ip_3",
        date: "2026-03-03",
        amount: 45_000,
        method: "Cash",
        reference: "CASH-0312",
      },
    ],
  },
  {
    id: "inv_04",
    number: "INV-2026-0061",
    studentName: "Ibrahim Musa",
    studentId: "TA-2023-0061",
    className: "SSS 3A",
    term: "2025/2026 · First Term",
    status: "Pending",
    dueDate: "2026-03-15",
    lineItems: [
      { id: "ili_12", label: "Tuition", amount: 200_000 },
      { id: "ili_13", label: "WAEC prep", amount: 40_000 },
    ],
    payments: [],
  },
  {
    id: "inv_05",
    number: "INV-2026-0034",
    studentName: "Ngozi Okafor",
    studentId: "TA-2025-0034",
    className: "Primary 5B",
    term: "2025/2026 · First Term",
    status: "Paid",
    dueDate: "2026-02-28",
    lineItems: [
      { id: "ili_14", label: "Tuition", amount: 90_000 },
      { id: "ili_15", label: "Books & materials", amount: 35_000 },
      { id: "ili_16", label: "Sports", amount: 8_000 },
    ],
    payments: [
      {
        id: "ip_4",
        date: "2026-03-02",
        amount: 133_000,
        method: "Transfer",
        reference: "TRF-771903",
      },
    ],
  },
];

export function invoiceTotal(invoice: Invoice): number {
  return invoice.lineItems.reduce((sum, item) => sum + item.amount, 0);
}

export function invoicePaid(invoice: Invoice): number {
  return invoice.payments.reduce((sum, p) => sum + p.amount, 0);
}

export function invoiceBalance(invoice: Invoice): number {
  return Math.max(0, invoiceTotal(invoice) - invoicePaid(invoice));
}

export const BURSAR_STUDENTS_FOR_PAYMENT = [
  { id: "stu_01", name: "Adaeze Okeke", studentId: "TA-2025-0142", invoiceId: "inv_01" },
  { id: "stu_02", name: "Tunde Balogun", studentId: "TA-2024-0088", invoiceId: "inv_02" },
  { id: "stu_03", name: "Chioma Eze", studentId: "TA-2025-0110", invoiceId: "inv_03" },
  { id: "stu_04", name: "Ibrahim Musa", studentId: "TA-2023-0061", invoiceId: "inv_04" },
  { id: "stu_05", name: "Ngozi Okafor", studentId: "TA-2025-0034", invoiceId: "inv_05" },
];

export const BURSAR_PAYMENT_ACCOUNT: PaymentAccount = {
  bankName: "Guaranty Trust Bank",
  accountName: "Test Academy Fees",
  accountNumberMasked: "**** **** 4821",
  accountNumberFull: "0123454821",
  verified: true,
};

export const GENERATE_WIZARD_CLASSES = [
  "JSS 1A",
  "JSS 1B",
  "JSS 2A",
  "SSS 2B",
  "Primary 5B",
];

export const GENERATE_PREVIEW_ROWS = [
  { studentName: "Adaeze Okeke", studentId: "TA-2025-0142", amount: 165_000 },
  { studentName: "Kemi Adeyemi", studentId: "TA-2025-0150", amount: 165_000 },
  { studentName: "David Okoro", studentId: "TA-2025-0158", amount: 165_000 },
  { studentName: "Fatima Bello", studentId: "TA-2025-0162", amount: 165_000 },
];
