export type TenantStatus = "Active" | "Trial" | "Suspended";

export type PlatformTenant = {
  id: string;
  name: string;
  subdomain: string;
  schema: string;
  status: TenantStatus;
  students: number;
  volumeNaira: number;
  commissionNaira: number;
};

export type WebhookStatus = "Delivered" | "Failed" | "Retrying";

export type WebhookLog = {
  id: string;
  time: string;
  event: string;
  tenant: string;
  status: WebhookStatus;
  httpStatus: number;
  payloadPreview: string;
  responseBody: string;
};

export const PLATFORM_REVENUE = {
  volumeThisMonth: 42_800_000,
  commissionThisMonth: 1_284_000,
  activeSchools: 28,
  failedWebhooks24h: 3,
};

export const PLATFORM_TENANTS: PlatformTenant[] = [
  {
    id: "ten_01",
    name: "Test Academy",
    subdomain: "testacademy",
    schema: "tenant_testacademy",
    status: "Active",
    students: 842,
    volumeNaira: 6_200_000,
    commissionNaira: 186_000,
  },
  {
    id: "ten_02",
    name: "Greenfield College",
    subdomain: "greenfield",
    schema: "tenant_greenfield",
    status: "Active",
    students: 1_204,
    volumeNaira: 9_100_000,
    commissionNaira: 273_000,
  },
  {
    id: "ten_03",
    name: "Harbor Lights School",
    subdomain: "harborlights",
    schema: "tenant_harborlights",
    status: "Trial",
    students: 210,
    volumeNaira: 480_000,
    commissionNaira: 14_400,
  },
  {
    id: "ten_04",
    name: "Unity Secondary",
    subdomain: "unitysec",
    schema: "tenant_unitysec",
    status: "Active",
    students: 956,
    volumeNaira: 5_400_000,
    commissionNaira: 162_000,
  },
  {
    id: "ten_05",
    name: "Sunrise Nursery",
    subdomain: "sunrise",
    schema: "tenant_sunrise",
    status: "Suspended",
    students: 88,
    volumeNaira: 0,
    commissionNaira: 0,
  },
];

export const PLATFORM_WEBHOOKS: WebhookLog[] = [
  {
    id: "wh_01",
    time: "2026-03-04T09:14:22Z",
    event: "charge.success",
    tenant: "testacademy",
    status: "Delivered",
    httpStatus: 200,
    payloadPreview: '{"event":"charge.success","data":{"amount":8500000,"currency":"NGN"}}',
    responseBody: '{"ok":true}',
  },
  {
    id: "wh_02",
    time: "2026-03-04T08:51:03Z",
    event: "transfer.failed",
    tenant: "greenfield",
    status: "Failed",
    httpStatus: 500,
    payloadPreview: '{"event":"transfer.failed","data":{"reference":"TRF-991"}}',
    responseBody: '{"error":"upstream timeout"}',
  },
  {
    id: "wh_03",
    time: "2026-03-04T07:22:41Z",
    event: "charge.success",
    tenant: "unitysec",
    status: "Delivered",
    httpStatus: 200,
    payloadPreview: '{"event":"charge.success","data":{"amount":12000000,"currency":"NGN"}}',
    responseBody: '{"ok":true}',
  },
  {
    id: "wh_04",
    time: "2026-03-03T22:05:18Z",
    event: "subscription.create",
    tenant: "harborlights",
    status: "Retrying",
    httpStatus: 429,
    payloadPreview: '{"event":"subscription.create","data":{"plan":"growth"}}',
    responseBody: '{"error":"rate_limited"}',
  },
  {
    id: "wh_05",
    time: "2026-03-03T18:40:09Z",
    event: "charge.success",
    tenant: "testacademy",
    status: "Delivered",
    httpStatus: 200,
    payloadPreview: '{"event":"charge.success","data":{"amount":4500000,"currency":"NGN"}}',
    responseBody: '{"ok":true}',
  },
];
