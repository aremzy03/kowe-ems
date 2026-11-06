"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Label,
  PageHeader,
  Select,
} from "@/components/ui";
import { academicsApi, type Arm, type ClassLevel, type Term } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type PublishResult = Awaited<ReturnType<typeof assessmentApi.publish>>;

function plural(count: number, singular: string, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

function describePublish(result: PublishResult): string[] {
  const lines: string[] = [];
  if (result.newly_published_count === 0) {
    lines.push(
      `Results were already published. ${plural(result.published_count, "student summary", "student summaries")} ${result.published_count === 1 ? "is" : "are"} on record, and nothing new was released.`,
    );
  } else if (result.newly_published_count === result.published_count) {
    lines.push(
      `Results published. ${plural(result.newly_published_count, "student summary", "student summaries")} ${result.newly_published_count === 1 ? "was" : "were"} released just now. Parents can open results and the report card.`,
    );
  } else {
    lines.push(
      `Results published. ${plural(result.newly_published_count, "student summary", "student summaries")} ${result.newly_published_count === 1 ? "was" : "were"} released just now. ${plural(result.published_count, "summary", "summaries")} ${result.published_count === 1 ? "is" : "are"} published in total.`,
    );
  }
  if (result.students_without_summary > 0) {
    const missing = result.students_without_summary;
    lines.push(
      `${plural(missing, "enrolled student")} ${missing === 1 ? "has" : "have"} no result summary, so ${missing === 1 ? "that student stays" : "they stay"} unpublished until this class is recomputed.`,
    );
  }
  const when = new Date(result.published_at);
  if (!Number.isNaN(when.getTime())) {
    lines.push(
      `Marked published ${new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(when)}.`,
    );
  }
  return lines;
}

function publishErrorMessage(err: unknown): string {
  if (!(err instanceof ApiRequestError)) {
    return err instanceof Error ? err.message : "Publish failed";
  }
  const mapped = mapDrfErrors(err.data);
  if (mapped.form) return mapped.form;
  const fieldText = Object.values(mapped.fields).filter(Boolean).join(" ");
  if (fieldText) return fieldText;
  return err.message;
}

export default function AdminPublishResultsPage() {
  const levels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const arms = useQuery({
    queryKey: ["academics", "arms"],
    queryFn: () => academicsApi.arms.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });

  const [classLevel, setClassLevel] = useState("");
  const [arm, setArm] = useState("");
  const [term, setTerm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PublishResult | null>(null);

  const levelOptions = useMemo(() => {
    return [...(levels.data ?? [])].sort((a: ClassLevel, b: ClassLevel) => {
      const byOrder = (a.order ?? 0) - (b.order ?? 0);
      if (byOrder !== 0) return byOrder;
      return a.name.localeCompare(b.name);
    });
  }, [levels.data]);

  const armOptions = useMemo(() => {
    return (arms.data ?? [])
      .filter((item: Arm) => item.class_level === classLevel)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [arms.data, classLevel]);

  const sessionNames = useMemo(() => {
    return new Map((sessions.data ?? []).map((session) => [session.id, session.name]));
  }, [sessions.data]);

  const catalogError = levels.error ?? arms.error ?? terms.error;
  const catalogsLoading = levels.isLoading || arms.isLoading || terms.isLoading;
  const ready = Boolean(classLevel && arm && term);

  const publish = useMutation({
    mutationFn: () =>
      assessmentApi.publish({
        class_level: classLevel,
        arm,
        term,
      }),
    onMutate: () => {
      setError(null);
      setResult(null);
    },
    onSuccess: (data) => {
      setResult(data);
    },
    onError: (err) => {
      setError(publishErrorMessage(err));
    },
  });

  function onClassLevelChange(next: string) {
    setClassLevel(next);
    setArm((current) => {
      const stillValid = (arms.data ?? []).some(
        (item) => item.id === current && item.class_level === next,
      );
      return stillValid ? current : "";
    });
    setResult(null);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Publish results"
        description="Release one class arm for a term. Parents see scores and the report card only after this."
      />

      {catalogError ? (
        <p className="text-sm text-danger">
          {catalogError instanceof Error
            ? catalogError.message
            : "Could not load classes and terms."}
        </p>
      ) : null}
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Class, arm, and term</CardTitle>
        </CardHeader>
        <CardBody>
          <form
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              if (!ready || publish.isPending) return;
              publish.mutate();
            }}
          >
            <div>
              <Label htmlFor="publish-class-level">Class level</Label>
              <Select
                id="publish-class-level"
                value={classLevel}
                disabled={catalogsLoading}
                onChange={(event) => onClassLevelChange(event.target.value)}
              >
                <option value="">
                  {catalogsLoading ? "Loading…" : "Select class level"}
                </option>
                {levelOptions.map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="publish-arm">Arm</Label>
              <Select
                id="publish-arm"
                value={arm}
                disabled={!classLevel || catalogsLoading}
                onChange={(event) => {
                  setArm(event.target.value);
                  setResult(null);
                }}
              >
                <option value="">
                  {classLevel ? "Select arm" : "Select a class level first"}
                </option>
                {armOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="publish-term">Term</Label>
              <Select
                id="publish-term"
                value={term}
                disabled={catalogsLoading}
                onChange={(event) => {
                  setTerm(event.target.value);
                  setResult(null);
                }}
              >
                <option value="">
                  {catalogsLoading ? "Loading…" : "Select term"}
                </option>
                {(terms.data ?? []).map((item: Term) => {
                  const sessionName = sessionNames.get(item.session);
                  return (
                    <option key={item.id} value={item.id}>
                      {sessionName ? `${item.name} · ${sessionName}` : item.name}
                    </option>
                  );
                })}
              </Select>
            </div>
            <div>
              <Button
                type="submit"
                size="sm"
                disabled={!ready || publish.isPending || catalogsLoading}
              >
                {publish.isPending ? "Publishing…" : "Publish results"}
              </Button>
            </div>
          </form>
          <p className="mt-3 text-sm text-ink/70">
            This does not recompute scores. Summaries must already exist for the class.
          </p>
        </CardBody>
      </Card>

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle>Publish result</CardTitle>
          </CardHeader>
          <CardBody className="space-y-2 text-sm">
            {describePublish(result).map((line) => (
              <p key={line}>{line}</p>
            ))}
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
