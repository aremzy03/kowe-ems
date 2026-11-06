"use client";

import { Card, CardBody, EmptyState, PageHeader } from "@/components/ui";

export default function TenantsPage() {
  return (
    <div>
      <PageHeader
        title="Tenants"
        description="Tenant provisioning is not exposed by EMS-api MVP"
      />
      <Card>
        <CardBody>
          <EmptyState
            headline="No tenant list API"
            body="Only GET /api/platform/revenue/ is available. Do not invent provision endpoints in the UI."
          />
        </CardBody>
      </Card>
    </div>
  );
}
