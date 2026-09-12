import type { ReactNode } from "react";
import clsx from "clsx";

interface CardProps {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}

export function Card({ children, className, padded = true }: CardProps) {
  return (
    <div
      className={clsx(
        "glass rounded-2xl border border-[var(--color-border)]",
        padded && "p-5",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h3 className="text-sm font-semibold tracking-wide text-[var(--color-text)]">
          {title}
        </h3>
        {subtitle && (
          <p className="text-xs text-[var(--color-text-muted)] mt-1">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}
