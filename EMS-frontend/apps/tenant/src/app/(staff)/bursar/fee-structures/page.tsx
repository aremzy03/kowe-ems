"use client";

import { FeeStructuresPanel } from "@/components/finance/FeeStructuresPanel";
import { PageHeader } from "@/components/ui";

export default function FeeStructuresPage() {
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
