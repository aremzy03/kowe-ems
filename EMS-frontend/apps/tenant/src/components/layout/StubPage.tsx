import { Card, CardBody, PageHeader } from "@/components/ui";

type StubPageProps = {
  title: string;
  description?: string;
};

export function StubPage({
  title,
  description = "Mock shell placeholder — full screens arrive in later phases.",
}: StubPageProps) {
  return (
    <div className="mx-auto w-full max-w-5xl">
      <PageHeader title={title} description={description} />
      <Card>
        <CardBody>
          <p className="text-ink/80">
            This route exists so navigation works during the UI shell build.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
