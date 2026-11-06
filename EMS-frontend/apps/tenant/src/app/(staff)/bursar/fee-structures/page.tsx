"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  Input,
  Label,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function FeeStructuresPage() {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["finance", "fee-structures"],
    queryFn: () => financeApi.feeStructures.list(),
  });
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => financeApi.feeStructures.create({ name }),
    onSuccess: () => {
      setName("");
      void qc.invalidateQueries({ queryKey: ["finance", "fee-structures"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Fee structures" description="Tuition and levy schemes" />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody className="flex flex-wrap items-end gap-3">
          <div className="min-w-[12rem] flex-1">
            <Label htmlFor="fs-name">Name</Label>
            <Input id="fs-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <Button
            size="sm"
            disabled={!name || create.isPending}
            onClick={() => create.mutate()}
          >
            Create
          </Button>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="p-0">
          {list.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : (list.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No fee structures"
                body="Create a structure to begin invoicing."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Id</TH>
                </TR>
              </THead>
              <TBody>
                {(list.data ?? []).map((fs) => (
                  <TR key={fs.id}>
                    <TD>{fs.name}</TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>{fs.id}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
