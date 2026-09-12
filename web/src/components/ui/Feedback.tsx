import type { ReactNode } from "react";

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      className="inline-block rounded-full border-2 border-current border-t-transparent animate-spin text-[var(--color-accent)]"
      style={{ width: size, height: size }}
    />
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      {icon && (
        <div className="h-12 w-12 rounded-2xl flex items-center justify-center bg-white/[0.03] border border-[var(--color-border)] text-[var(--color-text-muted)] mb-4">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-[var(--color-text)]">{title}</p>
      {description && (
        <p className="text-xs text-[var(--color-text-muted)] mt-1.5 max-w-xs">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 text-[var(--color-danger)] text-sm px-4 py-3">
      {message}
    </div>
  );
}
