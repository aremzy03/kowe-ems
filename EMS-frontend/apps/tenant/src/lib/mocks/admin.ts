/** Admin UI shell mocks — Nigerian K–12 context, session 2025/2026. No fetch(). */

export type AdminKpi = {
  label: string;
  value: string;
  delta?: string;
  accentTop?: "accent-1" | "accent-2" | "warning" | "danger";
};

export type NeedsAttentionItem = {
  id: string;
  title: string;
  detail: string;
  severity: "warning" | "danger" | "info";
};

export type CollectionBar = {
  label: string;
  collectedNaira: number;
  expectedNaira: number;
};

export type AcademicSession = {
  id: string;
  name: string;
  isCurrent: boolean;
};

export type AcademicTerm = {
  id: string;
  sessionId: string;
  name: string;
  isCurrent: boolean;
};

export type ClassLevel = {
  id: string;
  name: string;
};

export type ClassArm = {
  id: string;
  levelId: string;
  name: string;
  label: string;
};

export type Subject = {
  id: string;
  code: string;
  name: string;
};

export type AdminStudent = {
  id: string;
  admissionNo: string;
  name: string;
  classLabel: string;
  linkingCode: string;
  gender: "F" | "M";
};

export type EnrollmentStudent = {
  id: string;
  admissionNo: string;
  name: string;
};

export type StaffMember = {
  id: string;
  name: string;
  email: string;
  role: "admin" | "teacher" | "bursar";
  status: "active" | "inactive";
};

export type StaffInvite = {
  id: string;
  email: string;
  role: "admin" | "teacher" | "bursar";
  invitedAt: string;
};

export type SubjectAssignment = {
  id: string;
  subject: string;
  classLabel: string;
  teacherName: string;
};

export type FormTeacherAssignment = {
  id: string;
  classLabel: string;
  teacherName: string;
};

export type AttendanceClassRow = {
  id: string;
  classLabel: string;
  submitted: boolean;
  present: number;
  absent: number;
  late: number;
  formTeacher: string;
};

export type FeeClassRow = {
  id: string;
  classLabel: string;
  expectedNaira: number;
  collectedNaira: number;
  outstandingNaira: number;
  collectionPct: number;
};

export const ADMIN_DASHBOARD_KPIS: AdminKpi[] = [
  {
    label: "Students",
    value: "842",
    delta: "+18 this term",
    accentTop: "accent-1",
  },
  {
    label: "Fee collection",
    value: "78%",
    delta: "₦48.2M of ₦61.8M",
    accentTop: "accent-2",
  },
  {
    label: "Attendance today",
    value: "94%",
    delta: "791 of 842 present",
    accentTop: "warning",
  },
  {
    label: "Pending mark entry",
    value: "12",
    delta: "3 subjects overdue",
    accentTop: "danger",
  },
];

export const ADMIN_NEEDS_ATTENTION: NeedsAttentionItem[] = [
  {
    id: "att_01",
    title: "JSS 2B attendance not submitted",
    detail: "Form teacher: Kemi Adebayo · as of 9:40 AM",
    severity: "danger",
  },
  {
    id: "att_02",
    title: "SSS 1A Mathematics CA2 overdue",
    detail: "Deadline was yesterday · Ibrahim Musa",
    severity: "warning",
  },
  {
    id: "att_03",
    title: "Fee arrears: JSS 3C above 40%",
    detail: "₦1.8M outstanding · 22 students",
    severity: "warning",
  },
  {
    id: "att_04",
    title: "3 pending staff invites",
    detail: "Expires in 5 days if not accepted",
    severity: "info",
  },
];

export const ADMIN_COLLECTION_BARS: CollectionBar[] = [
  { label: "JSS 1", collectedNaira: 6_200_000, expectedNaira: 7_500_000 },
  { label: "JSS 2", collectedNaira: 5_800_000, expectedNaira: 7_200_000 },
  { label: "JSS 3", collectedNaira: 4_900_000, expectedNaira: 6_800_000 },
  { label: "SSS 1", collectedNaira: 9_100_000, expectedNaira: 11_000_000 },
  { label: "SSS 2", collectedNaira: 11_400_000, expectedNaira: 14_200_000 },
  { label: "SSS 3", collectedNaira: 10_800_000, expectedNaira: 15_100_000 },
];

export const INITIAL_SESSIONS: AcademicSession[] = [
  { id: "ses_2526", name: "2025/2026", isCurrent: true },
  { id: "ses_2425", name: "2024/2025", isCurrent: false },
];

export const INITIAL_TERMS: AcademicTerm[] = [
  { id: "term_1", sessionId: "ses_2526", name: "First Term", isCurrent: true },
  { id: "term_2", sessionId: "ses_2526", name: "Second Term", isCurrent: false },
  { id: "term_3", sessionId: "ses_2526", name: "Third Term", isCurrent: false },
];

export const INITIAL_LEVELS: ClassLevel[] = [
  { id: "lvl_jss1", name: "JSS 1" },
  { id: "lvl_jss2", name: "JSS 2" },
  { id: "lvl_jss3", name: "JSS 3" },
  { id: "lvl_sss1", name: "SSS 1" },
  { id: "lvl_sss2", name: "SSS 2" },
  { id: "lvl_sss3", name: "SSS 3" },
];

export const INITIAL_ARMS: ClassArm[] = [
  { id: "arm_jss1a", levelId: "lvl_jss1", name: "A", label: "JSS 1A" },
  { id: "arm_jss1b", levelId: "lvl_jss1", name: "B", label: "JSS 1B" },
  { id: "arm_jss2a", levelId: "lvl_jss2", name: "A", label: "JSS 2A" },
  { id: "arm_sss1a", levelId: "lvl_sss1", name: "A", label: "SSS 1A" },
  { id: "arm_sss2b", levelId: "lvl_sss2", name: "B", label: "SSS 2B" },
];

export const INITIAL_SUBJECTS: Subject[] = [
  { id: "sub_eng", code: "ENG", name: "English Language" },
  { id: "sub_mat", code: "MAT", name: "Mathematics" },
  { id: "sub_bsc", code: "BSC", name: "Basic Science" },
  { id: "sub_bss", code: "BSS", name: "Basic Technology" },
  { id: "sub_civ", code: "CIV", name: "Civic Education" },
  { id: "sub_yor", code: "YOR", name: "Yoruba" },
];

export const INITIAL_STUDENTS: AdminStudent[] = [
  {
    id: "stu_01",
    admissionNo: "TA-2025-0142",
    name: "Adaeze Okeke",
    classLabel: "JSS 1A",
    linkingCode: "LINK-A7K2",
    gender: "F",
  },
  {
    id: "stu_02",
    admissionNo: "TA-2025-0143",
    name: "Chinedu Eze",
    classLabel: "JSS 1A",
    linkingCode: "LINK-B3M9",
    gender: "M",
  },
  {
    id: "stu_03",
    admissionNo: "TA-2025-0088",
    name: "Fatima Yusuf",
    classLabel: "JSS 1B",
    linkingCode: "LINK-C1P4",
    gender: "F",
  },
  {
    id: "stu_04",
    admissionNo: "TA-2024-0211",
    name: "Tunde Bakare",
    classLabel: "JSS 2A",
    linkingCode: "LINK-D8Q6",
    gender: "M",
  },
  {
    id: "stu_05",
    admissionNo: "TA-2023-0065",
    name: "Ngozi Okafor",
    classLabel: "SSS 1A",
    linkingCode: "LINK-E2R1",
    gender: "F",
  },
  {
    id: "stu_06",
    admissionNo: "TA-2023-0087",
    name: "Chukwudi Okeke",
    classLabel: "SSS 2B",
    linkingCode: "LINK-F5S3",
    gender: "M",
  },
  {
    id: "stu_07",
    admissionNo: "TA-2025-0150",
    name: "Aisha Bello",
    classLabel: "JSS 1A",
    linkingCode: "LINK-G9T7",
    gender: "F",
  },
  {
    id: "stu_08",
    admissionNo: "TA-2024-0199",
    name: "Emeka Nwosu",
    classLabel: "JSS 3C",
    linkingCode: "LINK-H4U0",
    gender: "M",
  },
];

export const INITIAL_NOT_ENROLLED_JSS1A: EnrollmentStudent[] = [
  { id: "enr_n1", admissionNo: "TA-2025-0201", name: "Blessing Adeola" },
  { id: "enr_n2", admissionNo: "TA-2025-0202", name: "Ifeanyi Okonkwo" },
  { id: "enr_n3", admissionNo: "TA-2025-0203", name: "Halima Abdullahi" },
  { id: "enr_n4", admissionNo: "TA-2025-0204", name: "David Ojo" },
];

export const INITIAL_ENROLLED_JSS1A: EnrollmentStudent[] = [
  { id: "enr_e1", admissionNo: "TA-2025-0142", name: "Adaeze Okeke" },
  { id: "enr_e2", admissionNo: "TA-2025-0143", name: "Chinedu Eze" },
  { id: "enr_e3", admissionNo: "TA-2025-0150", name: "Aisha Bello" },
  { id: "enr_e4", admissionNo: "TA-2025-0151", name: "Obinna Ike" },
  { id: "enr_e5", admissionNo: "TA-2025-0152", name: "Zainab Mohammed" },
];

export const INITIAL_STAFF_MEMBERS: StaffMember[] = [
  {
    id: "stf_01",
    name: "Ngozi Adeyemi",
    email: "admin@testacademy.ng",
    role: "admin",
    status: "active",
  },
  {
    id: "stf_02",
    name: "Ibrahim Musa",
    email: "teacher@testacademy.ng",
    role: "teacher",
    status: "active",
  },
  {
    id: "stf_03",
    name: "Funke Balogun",
    email: "bursar@testacademy.ng",
    role: "bursar",
    status: "active",
  },
  {
    id: "stf_04",
    name: "Kemi Adebayo",
    email: "kemi.adebayo@testacademy.ng",
    role: "teacher",
    status: "active",
  },
  {
    id: "stf_05",
    name: "Olumide Fashola",
    email: "olumide.fashola@testacademy.ng",
    role: "teacher",
    status: "inactive",
  },
];

export const INITIAL_STAFF_INVITES: StaffInvite[] = [
  {
    id: "inv_01",
    email: "grace.umenyi@gmail.com",
    role: "teacher",
    invitedAt: "2025-09-01",
  },
  {
    id: "inv_02",
    email: "segun.olatunji@yahoo.com",
    role: "teacher",
    invitedAt: "2025-09-02",
  },
  {
    id: "inv_03",
    email: "amaka.okeke@outlook.com",
    role: "bursar",
    invitedAt: "2025-09-03",
  },
];

export const SUBJECT_ASSIGNMENTS: SubjectAssignment[] = [
  {
    id: "sa_01",
    subject: "Mathematics",
    classLabel: "JSS 1A",
    teacherName: "Ibrahim Musa",
  },
  {
    id: "sa_02",
    subject: "English Language",
    classLabel: "JSS 1A",
    teacherName: "Kemi Adebayo",
  },
  {
    id: "sa_03",
    subject: "Basic Science",
    classLabel: "JSS 1B",
    teacherName: "Ibrahim Musa",
  },
  {
    id: "sa_04",
    subject: "Mathematics",
    classLabel: "SSS 1A",
    teacherName: "Olumide Fashola",
  },
  {
    id: "sa_05",
    subject: "Civic Education",
    classLabel: "SSS 2B",
    teacherName: "Kemi Adebayo",
  },
];

export const FORM_TEACHER_ASSIGNMENTS: FormTeacherAssignment[] = [
  { id: "ft_01", classLabel: "JSS 1A", teacherName: "Kemi Adebayo" },
  { id: "ft_02", classLabel: "JSS 1B", teacherName: "Ibrahim Musa" },
  { id: "ft_03", classLabel: "JSS 2A", teacherName: "Olumide Fashola" },
  { id: "ft_04", classLabel: "SSS 1A", teacherName: "Ngozi Adeyemi" },
];

export const ATTENDANCE_OVERVIEW_KPIS: AdminKpi[] = [
  {
    label: "School present rate",
    value: "94%",
    delta: "791 / 842",
    accentTop: "accent-1",
  },
  {
    label: "Classes submitted",
    value: "18 / 22",
    delta: "4 pending",
    accentTop: "warning",
  },
  {
    label: "Absent today",
    value: "38",
    delta: "13 excused",
    accentTop: "danger",
  },
  {
    label: "Late arrivals",
    value: "13",
    delta: "vs 9 yesterday",
    accentTop: "accent-2",
  },
];

export const ATTENDANCE_CLASS_ROWS: AttendanceClassRow[] = [
  {
    id: "ac_01",
    classLabel: "JSS 1A",
    submitted: true,
    present: 38,
    absent: 2,
    late: 1,
    formTeacher: "Kemi Adebayo",
  },
  {
    id: "ac_02",
    classLabel: "JSS 1B",
    submitted: true,
    present: 35,
    absent: 3,
    late: 2,
    formTeacher: "Ibrahim Musa",
  },
  {
    id: "ac_03",
    classLabel: "JSS 2B",
    submitted: false,
    present: 0,
    absent: 0,
    late: 0,
    formTeacher: "Kemi Adebayo",
  },
  {
    id: "ac_04",
    classLabel: "SSS 1A",
    submitted: true,
    present: 41,
    absent: 1,
    late: 0,
    formTeacher: "Ngozi Adeyemi",
  },
  {
    id: "ac_05",
    classLabel: "SSS 2B",
    submitted: true,
    present: 36,
    absent: 4,
    late: 3,
    formTeacher: "Olumide Fashola",
  },
];

export const FEE_OVERVIEW_KPIS: AdminKpi[] = [
  {
    label: "Expected this term",
    value: "₦61.8M",
    delta: "First Term · 2025/2026",
    accentTop: "accent-1",
  },
  {
    label: "Collected",
    value: "₦48.2M",
    delta: "78% of expected",
    accentTop: "accent-2",
  },
  {
    label: "Outstanding",
    value: "₦13.6M",
    delta: "187 invoices open",
    accentTop: "warning",
  },
  {
    label: "Overdue",
    value: "₦4.1M",
    delta: "62 students",
    accentTop: "danger",
  },
];

export const FEE_BY_CLASS: FeeClassRow[] = [
  {
    id: "fc_01",
    classLabel: "JSS 1A",
    expectedNaira: 3_750_000,
    collectedNaira: 3_200_000,
    outstandingNaira: 550_000,
    collectionPct: 85,
  },
  {
    id: "fc_02",
    classLabel: "JSS 1B",
    expectedNaira: 3_750_000,
    collectedNaira: 3_000_000,
    outstandingNaira: 750_000,
    collectionPct: 80,
  },
  {
    id: "fc_03",
    classLabel: "JSS 3C",
    expectedNaira: 4_500_000,
    collectedNaira: 2_700_000,
    outstandingNaira: 1_800_000,
    collectionPct: 60,
  },
  {
    id: "fc_04",
    classLabel: "SSS 1A",
    expectedNaira: 5_500_000,
    collectedNaira: 4_620_000,
    outstandingNaira: 880_000,
    collectionPct: 84,
  },
  {
    id: "fc_05",
    classLabel: "SSS 2B",
    expectedNaira: 7_100_000,
    collectedNaira: 5_680_000,
    outstandingNaira: 1_420_000,
    collectionPct: 80,
  },
];

export const ENROLLMENT_TARGET_CLASS = "JSS 1A";
export const ADMIN_SESSION_LABEL = "2025/2026 · First Term";

export function formatNaira(amount: number): string {
  if (amount >= 1_000_000) {
    const m = amount / 1_000_000;
    return `₦${m % 1 === 0 ? m.toFixed(0) : m.toFixed(1)}M`;
  }
  if (amount >= 1_000) {
    return `₦${Math.round(amount / 1_000)}k`;
  }
  return `₦${amount.toLocaleString("en-NG")}`;
}

export function nextLinkingCode(seed: number): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let n = seed;
  let code = "";
  for (let i = 0; i < 4; i++) {
    code += alphabet[n % alphabet.length];
    n = Math.floor(n / alphabet.length) + 17;
  }
  return `LINK-${code}`;
}

export function roleLabel(role: StaffMember["role"] | StaffInvite["role"]): string {
  if (role === "admin") return "Admin";
  if (role === "bursar") return "Bursar";
  return "Teacher";
}
