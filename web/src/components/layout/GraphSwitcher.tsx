import { useEffect, useRef, useState } from "react";
import { ChevronsUpDown, Check, Plus, Waypoints } from "lucide-react";
import { useGraphContext } from "../../lib/GraphContext";

export function GraphSwitcher() {
  const { currentGraphId, currentGraph, graphs, isLoading, selectGraph, createAndSelect } =
    useGraphContext();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
        setError(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    try {
      await createAndSelect(name);
      setNewName("");
      setCreating(false);
      setOpen(false);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create graph");
    }
  }

  return (
    <div ref={containerRef} className="relative px-3 py-3 border-b border-[var(--color-border-soft)]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 rounded-xl px-2.5 py-2 text-left hover:bg-white/[0.04] transition-colors"
      >
        <div className="h-6 w-6 rounded-lg bg-[var(--color-accent)]/12 text-[var(--color-accent)] flex items-center justify-center shrink-0">
          <Waypoints size={13} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium truncate">
            {isLoading ? "Loading…" : currentGraph?.name ?? "Select graph"}
          </div>
          {currentGraph && (
            <div className="text-[10px] text-[var(--color-text-faint)]">
              {currentGraph.node_count} nodes
            </div>
          )}
        </div>
        <ChevronsUpDown size={13} className="text-[var(--color-text-faint)] shrink-0" />
      </button>

      {open && (
        <div className="absolute left-3 right-3 top-full mt-1.5 z-30 glass border border-[var(--color-border)] rounded-xl p-1.5 shadow-lg">
          <div className="max-h-56 overflow-y-auto space-y-0.5">
            {graphs.map((g) => (
              <button
                key={g.id}
                onClick={() => {
                  selectGraph(g.id);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left hover:bg-white/[0.05] transition-colors"
              >
                <Check
                  size={13}
                  className="shrink-0"
                  style={{ opacity: g.id === currentGraphId ? 1 : 0, color: "var(--color-accent)" }}
                />
                <span className="text-xs flex-1 truncate">{g.name}</span>
                <span className="text-[10px] text-[var(--color-text-faint)]">{g.node_count}</span>
              </button>
            ))}
          </div>

          <div className="border-t border-[var(--color-border-soft)] mt-1.5 pt-1.5">
            {creating ? (
              <div className="px-1.5 space-y-1.5">
                <input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  placeholder="Graph name…"
                  className="w-full bg-black/30 border border-[var(--color-border)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--color-accent)]/50 placeholder:text-[var(--color-text-faint)]"
                />
                {error && <p className="text-[10px] text-[var(--color-danger)] px-0.5">{error}</p>}
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim()}
                  className="w-full text-xs font-medium rounded-lg bg-[var(--color-accent)] text-white py-1.5 disabled:opacity-40"
                >
                  Create
                </button>
              </div>
            ) : (
              <button
                onClick={() => setCreating(true)}
                className="w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.05] transition-colors"
              >
                <Plus size={13} />
                New graph
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
