"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { academicsApi } from "@/lib/api/academics";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type InviteRole = "teacher" | "bursar" | "admin";

export default function AdminStaffPage() {
  const queryClient = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<InviteRole>("teacher");
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<
    { email: string; role: InviteRole; at: string }[]
  >([]);

  function resetInvite() {
    setEmail("");
    setRole("teacher");
    setError(null);
  }

  const inviteMutation = useMutation({
    mutationFn: () =>
      academicsApi.createInvite(email.trim().toLowerCase(), role),
    onSuccess: () => {
      setRecent((prev) => [
        {
          email: email.trim().toLowerCase(),
          role,
          at: new Date().toISOString().slice(0, 10),
        },
        ...prev,
      ]);
      setInviteOpen(false);
      resetInvite();
      void queryClient.invalidateQueries({ queryKey: ["memberships"] });
    },
    onError: (err) => {
      if (err instanceof ApiRequestError) {
        setError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Invite failed");
      }
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Staff"
        description="Invite teachers, bursars, and admins (membership list API not in MVP)"
        actions={
          <Button size="sm" onClick={() => setInviteOpen(true)}>
            Invite staff
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardBody>
          <EmptyState
            headline="No staff directory API"
            body="EMS-api exposes invite create only. Accepted members appear after they complete /accept-invite."
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent invites (this session)</CardTitle>
        </CardHeader>
        <CardBody className="p-0 sm:p-0">
          {recent.length === 0 ? (
            <p className="p-4 text-sm text-ink/65">No invites sent yet.</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Email</TH>
                  <TH>Role</TH>
                  <TH>Invited</TH>
                </TR>
              </THead>
              <TBody>
                {recent.map((inv) => (
                  <TR key={`${inv.email}-${inv.at}`}>
                    <TD className="text-sm">{inv.email}</TD>
                    <TD>
                      <Badge variant="warning">{inv.role}</Badge>
                    </TD>
                    <TD
                      style={{ fontFamily: "var(--font-mono)" }}
                      className="text-sm"
                    >
                      {inv.at}
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
              onChange={(e) => setRole(e.target.value as InviteRole)}
            >
              <option value="teacher">Teacher</option>
              <option value="bursar">Bursar</option>
              <option value="admin">Admin</option>
            </Select>
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
        </div>
      </Modal>
    </div>
  );
}
