import { apiFetch } from "@/lib/api/client";
import type { Paginated } from "@/lib/api/academics";

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

export type NotificationStatus = "queued" | "sent" | "failed";
export type NotificationChannel = "email" | "whatsapp";
export type NotificationTrigger =
  | "invoice_generated"
  | "payment_confirmed"
  | "result_published";

export type NotificationLog = {
  id: string;
  recipient: string;
  recipient_email: string;
  recipient_name: string;
  channel: NotificationChannel;
  trigger_type: NotificationTrigger;
  status: NotificationStatus;
  related_object_id: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
};

export type NotificationListParams = {
  status?: NotificationStatus;
  trigger_type?: NotificationTrigger;
  channel?: NotificationChannel;
  created_from?: string;
  created_to?: string;
};

function listPath(params?: NotificationListParams): string {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.trigger_type) search.set("trigger_type", params.trigger_type);
  if (params?.channel) search.set("channel", params.channel);
  if (params?.created_from) search.set("created_from", params.created_from);
  if (params?.created_to) search.set("created_to", params.created_to);
  const qs = search.toString();
  return qs
    ? `/api/communications/notifications/?${qs}`
    : "/api/communications/notifications/";
}

export const communicationsApi = {
  notifications: {
    list: async (params?: NotificationListParams) => {
      const data = await apiFetch<Paginated<NotificationLog> | NotificationLog[]>(
        listPath(params),
        { auth: true },
      );
      return unwrapList(data);
    },
    resend: (id: string) =>
      apiFetch<NotificationLog>(
        `/api/communications/notifications/${id}/resend/`,
        { method: "POST", auth: true },
      ),
  },
};
