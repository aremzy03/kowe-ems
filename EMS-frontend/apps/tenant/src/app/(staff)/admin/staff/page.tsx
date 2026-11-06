"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  Input,
  Label,
  PageHeader,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Modal } from "@/components/ui/client";
import { ApiRequestError } from "@/lib/api/client";
import { formatApiError, mapDrfErrors } from "@/lib/api/errors";
import {
  membershipsApi,
  type MembershipRole,
  type SchoolMembership,
  type StaffRole,
} from "@/lib/api/memberships";

const STAFF_ROLES: StaffRole[] = ["teacher", "bursar", "admin"];

function memberName(m: SchoolMembership) {
  return [m.first_name, m.last_name].filter(Boolean).join(" ") || m.email;
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function roleBadgeVariant(role: MembershipRole) {
  if (role === "admin") return "info" as const;
  if (role === "bursar") return "warning" as const;
  return "default" as const;
}

export default function AdminStaffPage() {
  const queryClient = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<StaffRole>("teacher");
  const [formError, setFormError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const members = useQuery({
    queryKey: ["memberships", "members"],
    queryFn: () => membershipsApi.members.list(),
  });
  const invites = useQuery({
    queryKey: ["memberships", "invites"],
    queryFn: () => membershipsApi.invites.list(),
  });

  function resetInvite() {
    setEmail("");
    setRole("teacher");
    setFormError(null);
  }

  function invalidateStaff() {
    void queryClient.invalidateQueries({ queryKey: ["memberships"] });
  }

  const inviteMutation = useMutation({
    mutationFn: () =>
      membershipsApi.invites.create(email.trim().toLowerCase(), role),
    onSuccess: () => {
      setInviteOpen(false);
      resetInvite();
      setPageError(null);
      invalidateStaff();
    },
    onError: (err) => {
      if (err instanceof ApiRequestError) {
        setFormError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setFormError(err instanceof Error ? err.message : "Invite failed");
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: Partial<Pick<SchoolMembership, "role" | "is_active">>;
    }) => membershipsApi.members.update(id, body),
    onSuccess: () => {
      setPageError(null);
      invalidateStaff();
    },
    onError: (err) => {
      setPageError(formatApiError(err, "Could not update membership"));
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => membershipsApi.members.deactivate(id),
    onSuccess: () => {
      setPageError(null);
      invalidateStaff();
    },
    onError: (err) => {
      setPageError(formatApiError(err, "Could not deactivate membership"));
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => membershipsApi.invites.revoke(id),
    onSuccess: () => {
      setPageError(null);
      invalidateStaff();
    },
    onError: (err) => {
      setPageError(formatApiError(err, "Could not revoke invite"));
    },
  });

  const rowBusy =
    updateMutation.isPending || deactivateMutation.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Staff"
        description="Teachers, bursars, and admins at this school"
        actions={
          <Button size="sm" onClick={() => setInviteOpen(true)}>
            Invite staff
          </Button>
        }
      />

      {pageError ? <p className="text-sm text-danger">{pageError}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardBody className="p-0 sm:p-0">
          {members.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : members.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(members.error, "Failed to load staff")}
            </p>
          ) : (members.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No staff yet"
                body="Invite a teacher, bursar, or admin. They appear here after accepting."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Email</TH>
                  <TH>Role</TH>
                  <TH>Status</TH>
                  <TH>Joined</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(members.data ?? []).map((m) => (
                  <TR key={m.id}>
                    <TD className="text-sm">{memberName(m)}</TD>
                    <TD className="text-sm">{m.email}</TD>
                    <TD>
                      <Select
                        aria-label={`Role for ${m.email}`}
                        value={STAFF_ROLES.includes(m.role as StaffRole) ? m.role : "teacher"}
                        disabled={rowBusy}
                        onChange={(e) =>
                          updateMutation.mutate({
                            id: m.id,
                            body: { role: e.target.value as StaffRole },
                          })
                        }
                      >
                        <option value="teacher">Teacher</option>
                        <option value="bursar">Bursar</option>
                        <option value="admin">Admin</option>
                      </Select>
                    </TD>
                    <TD>
                      <Badge variant={m.is_active ? "success" : "danger"}>
                        {m.is_active ? "active" : "inactive"}
                      </Badge>
                    </TD>
                    <TD
                      style={{ fontFamily: "var(--font-mono)" }}
                      className="text-sm"
                    >
                      {formatDate(m.joined_at)}
                    </TD>
                    <TD>
                      {m.is_active ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={rowBusy}
                          onClick={() => deactivateMutation.mutate(m.id)}
                        >
                          Deactivate
                        </Button>
                      ) : (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={rowBusy}
                          onClick={() =>
                            updateMutation.mutate({
                              id: m.id,
                              body: { is_active: true },
                            })
                          }
                        >
                          Reactivate
                        </Button>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pending invites</CardTitle>
        </CardHeader>
        <CardBody className="p-0 sm:p-0">
          {invites.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : invites.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(invites.error, "Failed to load invites")}
            </p>
          ) : (invites.data?.length ?? 0) === 0 ? (
            <p className="p-4 text-sm text-ink/65">No pending invites.</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Email</TH>
                  <TH>Role</TH>
                  <TH>Expires</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(invites.data ?? []).map((inv) => (
                  <TR key={inv.id}>
                    <TD className="text-sm">{inv.email}</TD>
                    <TD>
                      <Badge variant={roleBadgeVariant(inv.role)}>{inv.role}</Badge>
                    </TD>
                    <TD
                      style={{ fontFamily: "var(--font-mono)" }}
                      className="text-sm"
                    >
                      {formatDate(inv.expires_at)}
                    </TD>
                    <TD>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={revokeMutation.isPending}
                        onClick={() => revokeMutation.mutate(inv.id)}
                      >
                        Revoke
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Modal
        open={inviteOpen}
        onClose={() => {
          setInviteOpen(false);
          resetInvite();
        }}
        title="Invite staff"
        footer={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setInviteOpen(false);
                resetInvite();
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => inviteMutation.mutate()}
              disabled={inviteMutation.isPending || !email.includes("@")}
            >
              {inviteMutation.isPending ? "Sending…" : "Send invite"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              placeholder="teacher@example.ng"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="invite-role">Role</Label>
            <Select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value as StaffRole)}
            >
              <option value="teacher">Teacher</option>
              <option value="bursar">Bursar</option>
              <option value="admin">Admin</option>
            </Select>
          </div>
          {formError ? <p className="text-sm text-danger">{formError}</p> : null}
        </div>
      </Modal>
    </div>
  );
}
