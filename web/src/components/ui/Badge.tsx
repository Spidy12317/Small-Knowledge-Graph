import clsx from "clsx";
import type { NodeType } from "../../lib/types";
import { NODE_COLORS, NODE_LABELS } from "../../lib/nodeStyle";

export function NodeTypeBadge({ type, className }: { type: NodeType; className?: string }) {
  const color = NODE_COLORS[type];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium border",
        className,
      )}
      style={{
        color,
        borderColor: `${color}40`,
        backgroundColor: `${color}14`,
      }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {NODE_LABELS[type]}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "success" | "danger" | "accent";
}) {
  const tones: Record<string, string> = {
    neutral: "text-[var(--color-text-muted)] border-[var(--color-border)] bg-white/[0.02]",
    success: "text-[var(--color-success)] border-[var(--color-success)]/30 bg-[var(--color-success)]/10",
    danger: "text-[var(--color-danger)] border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10",
    accent: "text-[var(--color-accent)] border-[var(--color-accent)]/30 bg-[var(--color-accent)]/10",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium border",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
