import { cn } from "@/lib/cn";

type KoweLockupProps = {
  className?: string;
  /** Horizontal lockup width in CSS pixels (min ~96 per guidelines). */
  width?: number;
  /** Reversed (paper/ink on dark) — auth stays on paper, so default is full colour. */
  reversed?: boolean;
};

const ASPECT = 861 / 256;

/**
 * Horizontal Kowe lockup (symbol + drawn wordmark). Auth / onboarding hero only.
 * Do not place in dense Operate chrome — use KoweMark there.
 */
export function KoweLockup({
  className,
  width = 200,
  reversed = false,
}: KoweLockupProps) {
  const w = Math.max(width, 96);
  const h = Math.round(w / ASPECT);
  const src = reversed
    ? "/brand/kowe-horizontal-reversed.svg"
    : "/brand/kowe-horizontal.svg";
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Kowe"
      width={w}
      height={h}
      className={cn("mx-auto h-auto max-w-full", className)}
    />
  );
}
