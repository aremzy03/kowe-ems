"use client";

import { Card, CardBody, EmptyState, PageHeader } from "@/components/ui";

export default function WebhooksPage() {
  return (
    <div>
      <PageHeader
        title="Webhooks"
        description="Paystack webhooks stay on Django"
      />
      <Card>
        <CardBody>
          <EmptyState
            headline="No webhook admin API"
            body="POST /api/webhooks/paystack/ is handled by EMS-api (no tenant header; tenant from subaccount). Not implemented in Next."
          />
        </CardBody>
      </Card>
    </div>
  );
}
