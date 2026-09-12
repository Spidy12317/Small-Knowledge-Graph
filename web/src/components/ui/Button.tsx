import type { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  icon?: ReactNode;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  loading,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const variants: Record<string, string> = {
    primary:
      "bg-[var(--color-accent)] text-white border border-[var(--color-accent)] hover:brightness-110 shadow-[0_0_0_1px_rgba(124,108,242,0.3),0_8px_20px_-8px_rgba(124,108,242,0.6)]",
    secondary:
      "bg-white/[0.03] text-[var(--color-text)] border border-[var(--color-border)] hover:bg-white/[0.06] hover:border-[var(--color-border)]",
    ghost: "bg-transparent text-[var(--color-text-muted)] border border-transparent hover:text-[var(--color-text)] hover:bg-white/[0.04]",
    danger:
      "bg-[var(--color-danger)]/10 text-[var(--color-danger)] border border-[var(--color-danger)]/30 hover:bg-[var(--color-danger)]/20",
  };
  const sizes: Record<string, string> = {
    sm: "text-xs px-2.5 py-1.5 rounded-lg gap-1.5",
    md: "text-sm px-4 py-2 rounded-xl gap-2",
  };

  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center font-medium transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}
