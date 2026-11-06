import { cn } from "@/lib/cn";

type EmsMarkProps = {
  className?: string;
  size?: number;
};

/** Placeholder brand mark until final logo assets exist */
export function EmsMark({ className, size = 32 }: EmsMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0", className)}
      aria-hidden
    >
      <rect
        x="1.5"
        y="1.5"
        width="29"
        height="29"
        rx="6"
        fill="var(--color-accent-1)"
        stroke="var(--color-ink)"
        strokeWidth="1.5"
      />
      <path
        d="M8 22V10h3.2l2.4 7.2L16 10H19.2v12h-2.6v-7.4L14.2 22h-2.4l-2.4-7.4V22H8zm14.5 0V10h2.8v12h-2.8z"
        fill="var(--color-paper-card)"
      />
    </svg>
  );
}
