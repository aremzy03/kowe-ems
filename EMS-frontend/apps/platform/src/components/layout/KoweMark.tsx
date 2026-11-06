import { cn } from "@/lib/cn";

type KoweMarkProps = {
  className?: string;
  size?: number;
};

export function KoweMark({ className, size = 32 }: KoweMarkProps) {
  const src =
    size < 24 ? "/brand/kowe-symbol-small.svg" : "/brand/kowe-symbol.svg";
  return (
    // eslint-disable-next-line @next/next/no-img-element
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
