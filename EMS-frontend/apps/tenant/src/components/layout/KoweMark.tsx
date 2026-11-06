import { cn } from "@/lib/cn";

type KoweMarkProps = {
  className?: string;
  /** Rendered edge length in CSS pixels. Under 24 uses the small-size cut. */
  size?: number;
};

/**
 * Official Ọ Tile symbol from the Kowe logo kit.
 * Prefer this over recreating the mark in markup.
 */
export function KoweMark({ className, size = 32 }: KoweMarkProps) {
  const src =
    size < 24 ? "/brand/kowe-symbol-small.svg" : "/brand/kowe-symbol.svg";
  return (
    // eslint-disable-next-line @next/next/no-img-element -- kit SVG; keep sharp without Image optimizer
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      className={cn("shrink-0", className)}
      aria-hidden
    />
  );
}

/** @deprecated Use KoweMark */
export const EmsMark = KoweMark;
