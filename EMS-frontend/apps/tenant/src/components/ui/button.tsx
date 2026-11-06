import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "inverted"
  | "destructive"
  | "ghost";

export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "border-ink bg-accent-1 text-paper-card shadow-nb hover:shadow-nb-lg",
  secondary:
    "border-ink bg-paper-card text-ink shadow-nb hover:shadow-nb-lg",
  inverted:
    "border-ink bg-ink text-paper-card shadow-nb hover:shadow-nb-lg",
  destructive:
    "border-ink bg-danger text-paper-card shadow-nb hover:shadow-nb-lg",
  ghost:
    "border-transparent bg-transparent text-ink shadow-none hover:border-ink hover:bg-paper-card hover:shadow-nb-sm",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-base",
  lg: "px-6 py-3 text-lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      type = "button",
      disabled,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled}
        className={cn(
          "nb-interactive inline-flex items-center justify-center gap-2 rounded-[var(--radius-nb)] border-2 font-semibold",
          "disabled:pointer-events-none disabled:opacity-50",
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        style={{ fontFamily: "var(--font-heading)" }}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
