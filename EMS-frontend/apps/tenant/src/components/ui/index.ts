export { Button, type ButtonProps, type ButtonVariant, type ButtonSize } from "./button";
export {
  Card,
  CardHeader,
  CardTitle,
  CardBody,
  type CardProps,
  type CardAccentTop,
} from "./card";
export { Input, type InputProps } from "./input";
export { Label, type LabelProps } from "./label";
export { Textarea, type TextareaProps } from "./textarea";
export { Select, type SelectProps } from "./select";
export { Badge, type BadgeProps, type BadgeVariant } from "./badge";
export { Table, THead, TBody, TR, TH, TD } from "./table";
export { EmptyState, type EmptyStateProps } from "./empty-state";
export { PageHeader, type PageHeaderProps } from "./page-header";
export { KpiCard, type KpiCardProps } from "./kpi-card";
export { Money, type MoneyProps } from "./money";

// Client-only primitives (Modal, Toast) live in `@/components/ui/client`
// so server pages can import this barrel without pulling client chunks.
