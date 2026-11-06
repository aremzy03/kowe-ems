import { cn } from "@/lib/cn";

type KoweLockupProps = {
  className?: string;
  width?: number;
  reversed?: boolean;
};

const ASPECT = 861 / 256;

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
