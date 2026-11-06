"use client";

import { FeeStructuresPanel } from "@/components/finance/FeeStructuresPanel";
import { PageHeader } from "@/components/ui";

/** Dedicated admin route — same create/list as bursar fee structures. */
export default function AdminFeeStructuresPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Fee structures"
        description="Tuition and levy schemes for invoicing"
      />
      <FeeStructuresPanel showHeading={false} />
    </div>
  );
}
