export type MockChild = {
  id: string;
  name: string;
  className: string;
  studentId: string;
};

export type AttendanceMark = "P" | "L" | "A";

export type ParentSubjectResult = {
  subject: string;
  score: number;
  grade: string;
};

export type ParentResultsSnapshot = {
  average: number;
  position: string;
  totalInClass: number;
  term: string;
  subjects: ParentSubjectResult[];
};

export type ParentAttendanceDay = {
  date: string;
  mark: AttendanceMark;
};

export type ParentAttendanceSnapshot = {
  present: number;
  late: number;
  absent: number;
  termLabel: string;
  days: ParentAttendanceDay[];
};

export type ParentFeeInvoice = {
  id: string;
  number: string;
  term: string;
  status: "Paid" | "Partial" | "Due" | "Overdue";
  total: number;
  balance: number;
  dueDate: string;
};

export type ParentHomeSnapshot = {
  resultsAverage: number;
  attendanceRate: number;
  feeBalance: number;
};

const INITIAL_CHILDREN: MockChild[] = [
  {
    id: "child_01",
    name: "Adaeze Okeke",
    className: "JSS 1A",
    studentId: "TA-2025-0142",
  },
  {
    id: "child_02",
    name: "Chukwudi Okeke",
    className: "SSS 2B",
    studentId: "TA-2023-0087",
  },
];

let children: MockChild[] = [...INITIAL_CHILDREN];
let selectedChildId: string = children[0].id;

export type ParentChildrenSnapshot = {
  children: MockChild[];
  selectedChildId: string;
};

/** Cached for useSyncExternalStore — must be referentially stable until mutate. */
let snapshot: ParentChildrenSnapshot = { children, selectedChildId };

const listeners = new Set<() => void>();

function refreshSnapshot() {
  snapshot = { children, selectedChildId };
}

function notify() {
  refreshSnapshot();
  listeners.forEach((listener) => listener());
}

export function subscribeParentChildren(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

export function getParentChildrenSnapshot(): ParentChildrenSnapshot {
  return snapshot;
}

export function getSelectedChild(): MockChild | null {
  return children.find((c) => c.id === selectedChildId) ?? children[0] ?? null;
}

export function selectChild(id: string) {
  if (children.some((c) => c.id === id)) {
    selectedChildId = id;
    notify();
  }
}

export function addMockChild(partial?: Partial<MockChild>): MockChild {
  const next: MockChild = {
    id: `child_${Date.now()}`,
    name: partial?.name ?? "New Linked Student",
    className: partial?.className ?? "JSS 1B",
    studentId:
      partial?.studentId ??
      `TA-2025-${String(1000 + children.length).padStart(4, "0")}`,
  };
  children = [...children, next];
  selectedChildId = next.id;
  notify();
  return next;
}

/** Demo helper — clear linked children to exercise empty states. */
export function clearMockChildren() {
  children = [];
  selectedChildId = "";
  notify();
}

export function restoreMockChildren() {
  children = [...INITIAL_CHILDREN];
  selectedChildId = children[0]?.id ?? "";
  notify();
}

/** Valid demo linking codes for mock redeem */
export const VALID_LINKING_CODES = ["LINK-JSS1A-OK", "TA-LINK-2025"];

const RESULTS_BY_CHILD: Record<string, ParentResultsSnapshot> = {
  child_01: {
    average: 78.4,
    position: "5th",
    totalInClass: 32,
    term: "2025/2026 · First Term",
    subjects: [
      { subject: "Mathematics", score: 82, grade: "A" },
      { subject: "English", score: 76, grade: "B" },
      { subject: "Basic Science", score: 88, grade: "A" },
      { subject: "Social Studies", score: 71, grade: "B" },
      { subject: "Computer Studies", score: 80, grade: "A" },
      { subject: "French", score: 68, grade: "C" },
    ],
  },
  child_02: {
    average: 71.2,
    position: "12th",
    totalInClass: 28,
    term: "2025/2026 · First Term",
    subjects: [
      { subject: "Mathematics", score: 64, grade: "C" },
      { subject: "English", score: 75, grade: "B" },
      { subject: "Physics", score: 70, grade: "B" },
      { subject: "Chemistry", score: 68, grade: "C" },
      { subject: "Biology", score: 79, grade: "B" },
      { subject: "Economics", score: 72, grade: "B" },
    ],
  },
};

function buildAttendanceDays(seed: number): ParentAttendanceDay[] {
  const marks: AttendanceMark[] = ["P", "P", "P", "L", "P", "A", "P", "P", "P", "L", "P", "P"];
  const days: ParentAttendanceDay[] = [];
  for (let i = 0; i < 20; i += 1) {
    const day = 1 + ((i + seed) % 28);
    days.push({
      date: `2026-02-${String(day).padStart(2, "0")}`,
      mark: marks[(i + seed) % marks.length],
    });
  }
  return days.sort((a, b) => a.date.localeCompare(b.date));
}

const ATTENDANCE_BY_CHILD: Record<string, ParentAttendanceSnapshot> = {
  child_01: {
    present: 16,
    late: 2,
    absent: 2,
    termLabel: "First Term (to date)",
    days: buildAttendanceDays(1),
  },
  child_02: {
    present: 14,
    late: 4,
    absent: 2,
    termLabel: "First Term (to date)",
    days: buildAttendanceDays(3),
  },
};

const FEES_BY_CHILD: Record<string, ParentFeeInvoice[]> = {
  child_01: [
    {
      id: "pfee_01",
      number: "INV-2026-0142",
      term: "2025/2026 · First Term",
      status: "Partial",
      total: 165_000,
      balance: 80_000,
      dueDate: "2026-02-28",
    },
    {
      id: "pfee_02",
      number: "INV-2025-0901",
      term: "2024/2025 · Third Term",
      status: "Paid",
      total: 150_000,
      balance: 0,
      dueDate: "2025-09-30",
    },
  ],
  child_02: [
    {
      id: "pfee_03",
      number: "INV-2026-0087",
      term: "2025/2026 · First Term",
      status: "Due",
      total: 235_000,
      balance: 235_000,
      dueDate: "2026-03-15",
    },
  ],
};

const HOME_BY_CHILD: Record<string, ParentHomeSnapshot> = {
  child_01: {
    resultsAverage: 78.4,
    attendanceRate: 90,
    feeBalance: 80_000,
  },
  child_02: {
    resultsAverage: 71.2,
    attendanceRate: 85,
    feeBalance: 235_000,
  },
};

export function getParentResults(childId: string): ParentResultsSnapshot | null {
  return RESULTS_BY_CHILD[childId] ?? null;
}

export function getParentAttendance(childId: string): ParentAttendanceSnapshot | null {
  return ATTENDANCE_BY_CHILD[childId] ?? null;
}

export function getParentFees(childId: string): ParentFeeInvoice[] {
  return FEES_BY_CHILD[childId] ?? [];
}

export function getParentHomeSnapshot(childId: string): ParentHomeSnapshot | null {
  return HOME_BY_CHILD[childId] ?? null;
}

export function getPayableInvoice(
  childId: string,
  invoiceId?: string | null,
): ParentFeeInvoice | null {
  const fees = getParentFees(childId);
  if (invoiceId) {
    return fees.find((f) => f.id === invoiceId) ?? null;
  }
  return fees.find((f) => f.balance > 0) ?? fees[0] ?? null;
}
