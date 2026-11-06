import { apiFetch } from "@/lib/api/client";
import type { Paginated } from "@/lib/api/academics";

function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : (data.results ?? []);
}

export type StaffRole = "admin" | "teacher" | "bursar";
export type MembershipRole = StaffRole | "parent";

export type SchoolMembership = {
  id: string;
  user: string;
  email: string;
  first_name: string;
  last_name: string;
  role: MembershipRole;
  is_active: boolean;
  joined_at: string;
};

export type StaffInvite = {
  id: string;
  email: string;
  role: StaffRole;
  status: "pending" | "accepted" | "expired";
  expires_at: string;
  created_at: string;
  accept_url?: string;
};

export type MembershipListParams = {
  role?: MembershipRole;
  is_active?: boolean;
};

function membersPath(params?: MembershipListParams): string {
  const search = new URLSearchParams();
  if (params?.role) search.set("role", params.role);
  if (params?.is_active !== undefined) {
    search.set("is_active", String(params.is_active));
  }
  const qs = search.toString();
  return qs ? `/api/memberships/members/?${qs}` : "/api/memberships/members/";
}

export const membershipsApi = {
  members: {
    list: async (params?: MembershipListParams) => {
      const data = await apiFetch<Paginated<SchoolMembership> | SchoolMembership[]>(
        membersPath(params),
        { auth: true },
      );
      return unwrapList(data);
    },
    get: (id: string) =>
      apiFetch<SchoolMembership>(`/api/memberships/members/${id}/`, {
        auth: true,
      }),
    update: (
      id: string,
      body: Partial<Pick<SchoolMembership, "role" | "is_active">>,
    ) =>
      apiFetch<SchoolMembership>(`/api/memberships/members/${id}/`, {
        method: "PATCH",
        body,
        auth: true,
      }),
    deactivate: (id: string) =>
      apiFetch(`/api/memberships/members/${id}/`, {
        method: "DELETE",
        auth: true,
      }),
  },
  invites: {
    list: async (params?: { status?: StaffInvite["status"] }) => {
      const search = new URLSearchParams();
      if (params?.status) search.set("status", params.status);
      const qs = search.toString();
      const data = await apiFetch<Paginated<StaffInvite> | StaffInvite[]>(
        qs ? `/api/memberships/invites/?${qs}` : "/api/memberships/invites/",
        { auth: true },
      );
      return unwrapList(data);
    },
    create: (email: string, role: StaffRole) =>
      apiFetch<StaffInvite>("/api/memberships/invites/", {
        method: "POST",
        body: { email, role },
        auth: true,
      }),
    revoke: (id: string) =>
      apiFetch(`/api/memberships/invites/${id}/`, {
        method: "DELETE",
        auth: true,
      }),
  },
};
