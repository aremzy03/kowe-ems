/** Teacher role mock data — ui-shell phase 08. No fetch(). */

export type AssessmentComponentId = "1st_ca" | "2nd_ca" | "exam";

export type TeacherAssignment = {
  id: string;
  className: string;
  subject: string;
  studentCount: number;
  pendingScores: number;
};

export type FormTeacherClass = {
  id: string;
  className: string;
  studentCount: number;
  attendanceDue: boolean;
};

export type PendingChip = {
  id: string;
  label: string;
  variant: "warning" | "danger" | "info";
  href: string;
};

export type MarkStudent = {
  id: string;
  admissionNumber: string;
  name: string;
};

export type ComponentWeight = {
  id: AssessmentComponentId;
  label: string;
  weight: number;
  maxScore: number;
};

export type BroadsheetSubject = {
  code: string;
  name: string;
};

export type BroadsheetRow = {
  studentId: string;
  admissionNumber: string;
  name: string;
  /** subject code → score */
  scores: Record<string, number>;
  total: number;
  average: number;
  position: number;
};

export type AttendanceStatus = "present" | "late" | "absent";

export type AttendanceStudent = {
  id: string;
  admissionNumber: string;
  name: string;
  status: AttendanceStatus;
};

export type RemarkStudent = {
  id: string;
  admissionNumber: string;
  name: string;
  remark: string;
};

export const TEACHER_GREETING = {
  name: "Ibrahim Musa",
  termLabel: "2025/2026 · First Term",
  schoolName: "Test Academy",
};

export const TEACHER_ASSIGNMENTS: TeacherAssignment[] = [
  {
    id: "asg_01",
    className: "JSS 1A",
    subject: "Mathematics",
    studentCount: 32,
    pendingScores: 8,
  },
  {
    id: "asg_02",
    className: "JSS 1B",
    subject: "Mathematics",
    studentCount: 30,
    pendingScores: 0,
  },
  {
    id: "asg_03",
    className: "JSS 2A",
    subject: "Basic Science",
    studentCount: 28,
    pendingScores: 12,
  },
];

export const FORM_TEACHER_CLASSES: FormTeacherClass[] = [
  {
    id: "ft_01",
    className: "JSS 1A",
    studentCount: 32,
    attendanceDue: true,
  },
];

export const PENDING_CHIPS: PendingChip[] = [
  {
    id: "pc_01",
    label: "8 scores draft — JSS 1A Maths",
    variant: "warning",
    href: "/teacher/marks",
  },
  {
    id: "pc_02",
    label: "Attendance due today — JSS 1A",
    variant: "danger",
    href: "/teacher/attendance",
  },
  {
    id: "pc_03",
    label: "12 scores pending — JSS 2A Science",
    variant: "warning",
    href: "/teacher/marks",
  },
  {
    id: "pc_04",
    label: "Remarks open — JSS 1A",
    variant: "info",
    href: "/teacher/remarks",
  },
];

export const ASSESSMENT_COMPONENTS: {
  id: AssessmentComponentId;
  label: string;
  maxScore: number;
}[] = [
  { id: "1st_ca", label: "1st CA", maxScore: 20 },
  { id: "2nd_ca", label: "2nd CA", maxScore: 20 },
  { id: "exam", label: "Exam", maxScore: 60 },
];

export const MARK_ENTRY_META = {
  className: "JSS 1A",
  subject: "Mathematics",
  assignmentId: "asg_01",
};

export const MARK_STUDENTS: MarkStudent[] = [
  { id: "st_01", admissionNumber: "TA-2025-0142", name: "Adaeze Okeke" },
  { id: "st_02", admissionNumber: "TA-2025-0143", name: "Chinedu Eze" },
  { id: "st_03", admissionNumber: "TA-2025-0144", name: "Fatima Bello" },
  { id: "st_04", admissionNumber: "TA-2025-0145", name: "Gabriel Okafor" },
  { id: "st_05", admissionNumber: "TA-2025-0146", name: "Halima Yusuf" },
  { id: "st_06", admissionNumber: "TA-2025-0147", name: "Ifeanyi Nwosu" },
  { id: "st_07", admissionNumber: "TA-2025-0148", name: "Joy Adeyemi" },
  { id: "st_08", admissionNumber: "TA-2025-0149", name: "Kelechi Okoro" },
  { id: "st_09", admissionNumber: "TA-2025-0150", name: "Lola Adebayo" },
  { id: "st_10", admissionNumber: "TA-2025-0151", name: "Musa Ibrahim" },
  { id: "st_11", admissionNumber: "TA-2025-0152", name: "Ngozi Umeh" },
  { id: "st_12", admissionNumber: "TA-2025-0153", name: "Oluwaseun Bakare" },
];

/** Initial scores keyed by `${componentId}:${studentId}` */
export const INITIAL_MARK_SCORES: Record<string, string> = {
  "1st_ca:st_01": "16",
  "1st_ca:st_02": "14",
  "1st_ca:st_03": "18",
  "1st_ca:st_04": "12",
  "1st_ca:st_05": "15",
  "1st_ca:st_06": "",
  "1st_ca:st_07": "17",
  "1st_ca:st_08": "",
  "1st_ca:st_09": "13",
  "1st_ca:st_10": "19",
  "1st_ca:st_11": "",
  "1st_ca:st_12": "11",
  "2nd_ca:st_01": "15",
  "2nd_ca:st_02": "13",
  "2nd_ca:st_03": "17",
  "exam:st_01": "48",
  "exam:st_02": "42",
};

export const MARKS_STORAGE_KEY = "ems_teacher_marks_draft_v1";

export const INITIAL_COMPONENT_WEIGHTS: ComponentWeight[] = [
  { id: "1st_ca", label: "1st CA", weight: 20, maxScore: 20 },
  { id: "2nd_ca", label: "2nd CA", weight: 20, maxScore: 20 },
  { id: "exam", label: "Exam", weight: 60, maxScore: 60 },
];

export const BROADSHEET_META = {
  className: "JSS 1A",
  termLabel: "2025/2026 · First Term",
};

export const BROADSHEET_SUBJECTS: BroadsheetSubject[] = [
  { code: "MTH", name: "Mathematics" },
  { code: "ENG", name: "English" },
  { code: "BSC", name: "Basic Science" },
  { code: "BST", name: "Basic Tech" },
  { code: "SOS", name: "Social Studies" },
  { code: "CCA", name: "CCA" },
  { code: "FRE", name: "French" },
  { code: "PHE", name: "PHE" },
];

export const BROADSHEET_ROWS: BroadsheetRow[] = [
  {
    studentId: "st_01",
    admissionNumber: "TA-2025-0142",
    name: "Adaeze Okeke",
    scores: {
      MTH: 79,
      ENG: 72,
      BSC: 81,
      BST: 68,
      SOS: 75,
      CCA: 70,
      FRE: 65,
      PHE: 88,
    },
    total: 598,
    average: 74.75,
    position: 2,
  },
  {
    studentId: "st_03",
    admissionNumber: "TA-2025-0144",
    name: "Fatima Bello",
    scores: {
      MTH: 84,
      ENG: 78,
      BSC: 80,
      BST: 74,
      SOS: 79,
      CCA: 76,
      FRE: 71,
      PHE: 85,
    },
    total: 627,
    average: 78.38,
    position: 1,
  },
  {
    studentId: "st_02",
    admissionNumber: "TA-2025-0143",
    name: "Chinedu Eze",
    scores: {
      MTH: 69,
      ENG: 64,
      BSC: 70,
      BST: 62,
      SOS: 66,
      CCA: 58,
      FRE: 55,
      PHE: 80,
    },
    total: 524,
    average: 65.5,
    position: 4,
  },
  {
    studentId: "st_07",
    admissionNumber: "TA-2025-0148",
    name: "Joy Adeyemi",
    scores: {
      MTH: 74,
      ENG: 77,
      BSC: 73,
      BST: 70,
      SOS: 72,
      CCA: 68,
      FRE: 66,
      PHE: 82,
    },
    total: 582,
    average: 72.75,
    position: 3,
  },
  {
    studentId: "st_05",
    admissionNumber: "TA-2025-0146",
    name: "Halima Yusuf",
    scores: {
      MTH: 61,
      ENG: 58,
      BSC: 64,
      BST: 55,
      SOS: 60,
      CCA: 52,
      FRE: 50,
      PHE: 75,
    },
    total: 475,
    average: 59.38,
    position: 6,
  },
  {
    studentId: "st_10",
    admissionNumber: "TA-2025-0151",
    name: "Musa Ibrahim",
    scores: {
      MTH: 71,
      ENG: 68,
      BSC: 69,
      BST: 66,
      SOS: 70,
      CCA: 64,
      FRE: 60,
      PHE: 78,
    },
    total: 546,
    average: 68.25,
    position: 5,
  },
];

export const ATTENDANCE_META = {
  className: "JSS 1A",
  dateLabel: "Fri, 4 Sep 2026",
};

export const INITIAL_ATTENDANCE: AttendanceStudent[] = [
  {
    id: "st_01",
    admissionNumber: "TA-2025-0142",
    name: "Adaeze Okeke",
    status: "present",
  },
  {
    id: "st_02",
    admissionNumber: "TA-2025-0143",
    name: "Chinedu Eze",
    status: "present",
  },
  {
    id: "st_03",
    admissionNumber: "TA-2025-0144",
    name: "Fatima Bello",
    status: "late",
  },
  {
    id: "st_04",
    admissionNumber: "TA-2025-0145",
    name: "Gabriel Okafor",
    status: "present",
  },
  {
    id: "st_05",
    admissionNumber: "TA-2025-0146",
    name: "Halima Yusuf",
    status: "absent",
  },
  {
    id: "st_06",
    admissionNumber: "TA-2025-0147",
    name: "Ifeanyi Nwosu",
    status: "present",
  },
  {
    id: "st_07",
    admissionNumber: "TA-2025-0148",
    name: "Joy Adeyemi",
    status: "present",
  },
  {
    id: "st_08",
    admissionNumber: "TA-2025-0149",
    name: "Kelechi Okoro",
    status: "present",
  },
  {
    id: "st_09",
    admissionNumber: "TA-2025-0150",
    name: "Lola Adebayo",
    status: "late",
  },
  {
    id: "st_10",
    admissionNumber: "TA-2025-0151",
    name: "Musa Ibrahim",
    status: "present",
  },
  {
    id: "st_11",
    admissionNumber: "TA-2025-0152",
    name: "Ngozi Umeh",
    status: "absent",
  },
  {
    id: "st_12",
    admissionNumber: "TA-2025-0153",
    name: "Oluwaseun Bakare",
    status: "present",
  },
];

export const INITIAL_REMARKS: RemarkStudent[] = [
  {
    id: "st_01",
    admissionNumber: "TA-2025-0142",
    name: "Adaeze Okeke",
    remark: "Excellent effort in Mathematics. Keep practising word problems.",
  },
  {
    id: "st_02",
    admissionNumber: "TA-2025-0143",
    name: "Chinedu Eze",
    remark: "Shows improvement. Needs more consistency with homework.",
  },
  {
    id: "st_03",
    admissionNumber: "TA-2025-0144",
    name: "Fatima Bello",
    remark: "Outstanding performance this term. A pleasure to teach.",
  },
  {
    id: "st_04",
    admissionNumber: "TA-2025-0145",
    name: "Gabriel Okafor",
    remark: "",
  },
  {
    id: "st_05",
    admissionNumber: "TA-2025-0146",
    name: "Halima Yusuf",
    remark: "Encourage more class participation and revision before CA.",
  },
  {
    id: "st_07",
    admissionNumber: "TA-2025-0148",
    name: "Joy Adeyemi",
    remark: "Reliable and attentive. Continue the good work.",
  },
];

export const REPORT_CARD_PREVIEW = {
  studentName: "Adaeze Okeke",
  admissionNumber: "TA-2025-0142",
  className: "JSS 1A",
  termLabel: "2025/2026 · First Term",
  subjects: [
    { name: "Mathematics", ca: 31, exam: 48, total: 79, grade: "B" },
    { name: "English", ca: 28, exam: 44, total: 72, grade: "B" },
    { name: "Basic Science", ca: 33, exam: 48, total: 81, grade: "A" },
  ],
  position: "2 of 32",
  teacherRemark:
    "Excellent effort in Mathematics. Keep practising word problems.",
  principalRemark: "A promising term. Maintain this pace.",
};

export function markScoreKey(
  componentId: AssessmentComponentId,
  studentId: string,
): string {
  return `${componentId}:${studentId}`;
}

export function countFilledScores(
  scores: Record<string, string>,
  componentId: AssessmentComponentId,
  students: MarkStudent[],
): { filled: number; empty: number; total: number } {
  let filled = 0;
  for (const student of students) {
    const value = scores[markScoreKey(componentId, student.id)]?.trim() ?? "";
    if (value !== "") filled += 1;
  }
  const total = students.length;
  return { filled, empty: total - filled, total };
}

export function sumComponentWeights(weights: ComponentWeight[]): number {
  return weights.reduce((sum, row) => sum + (Number.isFinite(row.weight) ? row.weight : 0), 0);
}
