"use client";

import { Card, CardBody, EmptyState, PageHeader } from "@/components/ui";

export default function BursarInvoicesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Invoices"
        description="Bursar invoice list is not exposed by EMS-api MVP"
      />
      <Card>
        <CardBody>
          <EmptyState
            headline="No invoice list endpoint"
            body="Use Generate invoices for class runs. Parents see balances via my-invoices/."
          />
        </CardBody>
      </Card>
    </div>
  );
}
