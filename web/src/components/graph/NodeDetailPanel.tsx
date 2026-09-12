import { ArrowUpRight, X } from "lucide-react";
import { NodeTypeBadge } from "../ui/Badge";
import { Spinner } from "../ui/Feedback";
import type { NodeDetail } from "../../lib/types";

export function NodeDetailPanel({
  detail,
  isLoading,
  onSelect,
  onClose,
}: {
  detail?: NodeDetail;
  isLoading?: boolean;
  onSelect: (nodeId: string) => void;
  onClose: () => void;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40">
        <Spinner />
      </div>
    );
  }
  if (!detail) return null;

  const { node, children, parents } = detail;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between gap-3 mb-3">
        <NodeTypeBadge type={node.node_type} />
        <button
          onClick={onClose}
          className="text-[var(--color-text-faint)] hover:text-[var(--color-text)] transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <h3 className="text-sm font-semibold leading-snug">{node.label}</h3>
      <p className="text-[10px] font-mono text-[var(--color-text-faint)] mt-1 break-all">
        {node.node_id}
      </p>

      {node.description && (
        <p className="text-xs text-[var(--color-text-muted)] mt-3 leading-relaxed">
          {node.description}
        </p>
      )}

      {node.raw_text && (
        <div className="mt-3 rounded-lg border border-[var(--color-border)] bg-black/30 p-3 max-h-40 overflow-y-auto">
          <p className="text-[11px] font-mono text-[var(--color-text-muted)] whitespace-pre-wrap leading-relaxed">
            {node.raw_text}
          </p>
        </div>
      )}

      {parents.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)] mb-2">
            Parents
          </p>
          <div className="space-y-1">
            {parents.map((p) => (
              <RelatedRow key={p.node_id} label={p.label} onClick={() => onSelect(p.node_id)} />
            ))}
          </div>
        </div>
      )}

      {children.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)] mb-2">
            Children ({children.length})
          </p>
          <div className="space-y-1 overflow-y-auto max-h-64 pr-1">
            {children.map((c) => (
              <RelatedRow key={c.node_id} label={c.label} onClick={() => onSelect(c.node_id)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function RelatedRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between gap-2 text-left text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.03] rounded-lg px-2.5 py-1.5 transition-colors group"
    >
      <span className="truncate">{label}</span>
      <ArrowUpRight
        size={12}
        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
      />
    </button>
  );
}
