import { NODE_COLORS, NODE_LABELS } from "../../lib/nodeStyle";
import type { NodeType } from "../../lib/types";

const TYPES: NodeType[] = ["central", "category", "data"];

export function GraphLegend() {
  return (
    <div className="absolute bottom-4 left-4 glass border border-[var(--color-border)] rounded-xl px-3.5 py-2.5 flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
      {TYPES.map((t) => (
        <div key={t} className="flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: NODE_COLORS[t] }}
          />
          {NODE_LABELS[t]}
        </div>
      ))}
    </div>
  );
}
