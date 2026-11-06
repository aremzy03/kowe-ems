import { cn } from "@/lib/cn";

const icons: Record<string, { d: string; viewBox?: string }> = {
  dashboard: {
    d: "M4 4h7v7H4V4zm9 0h7v4h-7V4zM4 13h7v7H4v-7zm9 6h7v4h-7v-4zm0-6h7v4h-7v-4z",
  },
  academics: {
    d: "M3 7.5L12 3l9 4.5v2.2L12 6.2 3 9.7V7.5zM5 11v6.2c2.2 1.2 4.5 1.8 7 1.8s4.8-.6 7-1.8V11L12 8.2 5 11z",
  },
  students: {
    d: "M12 12a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM5 19.5c.6-3.2 3.4-5 7-5s6.4 1.8 7 5",
  },
  staff: {
    d: "M8.5 11a2.75 2.75 0 100-5.5 2.75 2.75 0 000 5.5zM15.5 11.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3.5 19c.5-2.6 2.6-4 5-4s4.5 1.4 5 4M13 15.2c1.8-.4 3.8.5 4.5 3.8",
  },
  enrollment: {
    d: "M8 4h8v3H8V4zM5 9h14v11H5V9zm4 3h6M9 15h4",
  },
  assignments: {
    d: "M7 3h10v3H7V3zM5 8h14v13H5V8zm4 4h6M9 16h4",
  },
  attendance: {
    d: "M8 3h8v2H8V3zM5 6h14v15H5V6zm3 5l3 3 5-6",
  },
  fees: {
    d: "M12 3v18M7 8c1.2-1.5 2.8-2 5-2s4 .8 5 2.5c.6 1 .4 2.3-1 3.2-1.2.8-3.2 1.1-4.8 1.5S8 14 7.5 15.5C7 17 8 19 12 19s4.2-.8 5-2",
  },
  marks: {
    d: "M5 20l9-9 3 3-9 9H5v-3zM15.5 6.5l2-2 3 3-2 2-3-3z",
  },
  components: {
    d: "M4 6h7v5H4V6zm9 0h7v5h-7V6zM4 13h7v5H4v-5zm9 0h7v5h-7v-5z",
  },
  broadsheet: {
    d: "M4 5h16v14H4V5zm0 4h16M8 5v14M12 9v10M16 9v10",
  },
  remarks: {
    d: "M5 5h14v10H9l-4 4V5z",
  },
  invoices: {
    d: "M7 3h10l3 4v14H4V3h3zm0 0v4h10M8 12h8M8 16h6",
  },
  payments: {
    d: "M3 8h18v10H3V8zm0 3h18M7 16h4",
  },
  account: {
    d: "M4 7h16v12H4V7zm3 4h6M7 15h4M16 7V5H8v2",
  },
  home: {
    d: "M4 11.5L12 5l8 6.5V20H4v-8.5zM10 20v-6h4v6",
  },
};

function iconKeyForHref(href: string): keyof typeof icons {
  if (href.endsWith("/academics")) return "academics";
  if (href.endsWith("/students")) return "students";
  if (href.endsWith("/staff")) return "staff";
  if (href.endsWith("/enrollment")) return "enrollment";
  if (href.endsWith("/assignments")) return "assignments";
  if (href.endsWith("/attendance")) return "attendance";
  if (href.endsWith("/fees") || href.includes("fee-structures")) return "fees";
  if (href.endsWith("/marks")) return "marks";
  if (href.endsWith("/components")) return "components";
  if (href.endsWith("/broadsheet")) return "broadsheet";
  if (href.endsWith("/remarks")) return "remarks";
  if (href.includes("/invoices")) return "invoices";
  if (href.includes("/payments")) return "payments";
  if (href.includes("payment-account")) return "account";
  if (href.endsWith("/teacher") || href.endsWith("/parent")) return "home";
  return "dashboard";
}

export function StaffNavIcon({
  href,
  className,
}: {
  href: string;
  className?: string;
}) {
  const key = iconKeyForHref(href);
  const icon = icons[key];
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      className={cn(className)}
      aria-hidden
    >
      <path
        d={icon.d}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
