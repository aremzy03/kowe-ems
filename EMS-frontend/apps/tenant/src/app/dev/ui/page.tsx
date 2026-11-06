"use client";

import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  Input,
  KpiCard,
  Label,
  PageHeader,
  PencilAside,
  PencilBars,
  Select,
  Table,
  TBody,
  TD,
  Textarea,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Modal } from "@/components/ui/client";

export default function UiDevPage() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <main className="min-h-screen px-4 py-10 text-ink md:px-8">
      <div className="mx-auto max-w-5xl space-y-12">
        <PageHeader
          title="UI primitives"
          description="Paper Brutalism components — Test Academy sample copy (₦, JSS 1A)."
          actions={
            <Button variant="secondary" size="sm" onClick={() => setModalOpen(true)}>
              Open modal
            </Button>
          }
        />

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Buttons
          </h2>
          <div className="flex flex-wrap gap-3">
            <Button variant="primary">Save scores</Button>
            <Button variant="secondary">Cancel</Button>
            <Button variant="inverted">Export CSV</Button>
            <Button variant="destructive">Delete class</Button>
            <Button variant="ghost">Clear filters</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
            <Button variant="secondary" disabled>
              Disabled
            </Button>
          </div>
        </section>

        <PencilAside>₦480,000.00 is still outstanding on 23 unpaid invoices.</PencilAside>

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Cards & KPIs
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="Fees collected"
              value="₦2.4M"
              delta="+12% vs last term"
              tone="green"
              series={[1.8, 1.9, 2.1, 2.0, 2.4]}
            />
            <KpiCard
              label="Outstanding"
              value="₦480k"
              delta="23 invoices overdue"
              tone="coral"
            />
            <KpiCard
              label="Present today"
              value="312"
              delta="JSS 1A · 94%"
              tone="green"
              rate={94}
              rateTone="green"
            />
            <Card accentTop="danger">
              <CardHeader>
                <CardTitle>Alert</CardTitle>
              </CardHeader>
              <CardBody>
                <p className="text-sm">3 students in JSS 1A marked absent without excuse.</p>
              </CardBody>
            </Card>
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Forms
          </h2>
          <Card>
            <CardBody className="grid max-w-md gap-4">
              <div>
                <Label htmlFor="student-name">Student name</Label>
                <Input id="student-name" placeholder="Chioma Okafor" defaultValue="Adaeze Nwosu" />
              </div>
              <div>
                <Label htmlFor="class">Class</Label>
                <Select id="class" defaultValue="jss1a">
                  <option value="jss1a">JSS 1A</option>
                  <option value="jss1b">JSS 1B</option>
                  <option value="ss2c">SS 2C</option>
                </Select>
              </div>
              <div>
                <Label htmlFor="notes">Notes</Label>
                <Textarea
                  id="notes"
                  placeholder="Term remarks…"
                  defaultValue="Strong in Mathematics. Needs support in English comprehension."
                />
              </div>
              <Button type="submit" className="w-fit">
                Save student
              </Button>
            </CardBody>
          </Card>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Badges
          </h2>
          <div className="flex flex-wrap gap-2">
            <Badge variant="default">Draft</Badge>
            <Badge variant="success">Paid</Badge>
            <Badge variant="warning">Partial</Badge>
            <Badge variant="danger">Overdue</Badge>
            <Badge variant="info">In review</Badge>
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Weekday roll
          </h2>
          <Card>
            <CardHeader>
              <CardTitle>JSS 1A this week</CardTitle>
            </CardHeader>
            <CardBody>
              <PencilBars
                points={[
                  { label: "Mon", value: 88, marked: 32 },
                  { label: "Tue", value: 94, marked: 32 },
                  { label: "Wed", value: 98, marked: 32 },
                  { label: "Thu", value: 91, marked: 31 },
                  { label: "Fri", value: 85, marked: 30 },
                ]}
              />
            </CardBody>
          </Card>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Table
          </h2>
          <Card ledger>
          <Table>
            <THead>
              <TR>
                <TH>Student</TH>
                <TH>Class</TH>
                <TH>Fee balance</TH>
                <TH>Status</TH>
              </TR>
            </THead>
            <TBody>
              <TR>
                <TD>Adaeze Nwosu</TD>
                <TD>JSS 1A</TD>
                <TD style={{ fontFamily: "var(--font-mono)" }}>₦0</TD>
                <TD>
                  <Badge variant="success">Paid</Badge>
                </TD>
              </TR>
              <TR>
                <TD>Tunde Bakare</TD>
                <TD>JSS 1A</TD>
                <TD style={{ fontFamily: "var(--font-mono)" }}>₦45,000</TD>
                <TD>
                  <Badge variant="danger">Overdue</Badge>
                </TD>
              </TR>
              <TR>
                <TD>Fatima Yusuf</TD>
                <TD>SS 2C</TD>
                <TD style={{ fontFamily: "var(--font-mono)" }}>₦15,000</TD>
                <TD>
                  <Badge variant="warning">Partial</Badge>
                </TD>
              </TR>
            </TBody>
          </Table>
          </Card>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
            Empty state
          </h2>
          <EmptyState
            headline="No assessments yet"
            body="Test Academy has not published Mid-Term for JSS 1A. Create one to start entering scores."
            primaryAction={<Button>Create assessment</Button>}
            secondaryAction={<Button variant="secondary">View classes</Button>}
          />
        </section>

        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Confirm fee waiver"
          footer={
            <>
              <Button variant="secondary" onClick={() => setModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={() => setModalOpen(false)}>
                Approve waiver
              </Button>
            </>
          }
        >
          <p>
            Waive ₦45,000 outstanding for <strong>Tunde Bakare</strong> (JSS 1A) at Test
            Academy? This will mark the invoice as paid.
          </p>
        </Modal>
      </div>
    </main>
  );
}
