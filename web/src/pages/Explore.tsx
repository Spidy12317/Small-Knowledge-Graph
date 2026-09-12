import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Search, Waypoints } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GraphLegend } from "../components/graph/GraphLegend";
import { NodeDetailPanel } from "../components/graph/NodeDetailPanel";
import { Button } from "../components/ui/Button";
import { EmptyState, Spinner } from "../components/ui/Feedback";
import { NodeTypeBadge } from "../components/ui/Badge";
import { api } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";
import type { GraphData, NodeType } from "../lib/types";

const ALL_TYPES: NodeType[] = ["central", "category", "data"];

function filterByTypes(data: GraphData, visible: Set<NodeType>): GraphData {
  if (visible.size === ALL_TYPES.length) return data;
  const nodes = data.nodes.filter((n) => visible.has(n.node_type));
  const nodeIds = new Set(nodes.map((n) => n.node_id));
  const edges = data.edges.filter(
    (e) => nodeIds.has(e.source_id) && nodeIds.has(e.target_id),
  );
  return { ...data, nodes, edges };
}

export function Explore() {
  const queryClient = useQueryClient();
  const { currentGraphId, selectGraph } = useGraphContext();
  const { data, isLoading } = useQuery({
    queryKey: ["graph", currentGraphId],
    queryFn: () => api.getGraph(currentGraphId),
    enabled: !!currentGraphId,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [visibleTypes, setVisibleTypes] = useState<Set<NodeType>>(new Set(ALL_TYPES));

  const detailQuery = useQuery({
    queryKey: ["node", currentGraphId, selectedId],
    queryFn: () => api.getNode(selectedId as string, currentGraphId),
    enabled: !!selectedId,
  });

  const resetMutation = useMutation({
    mutationFn: () => api.resetGraph(currentGraphId),
    onSuccess: (graph) => {
      queryClient.setQueryData(["graph", graph.graph_id], graph);
      queryClient.invalidateQueries({ queryKey: ["graphs"] });
      selectGraph(graph.graph_id);
      setSelectedId(null);
    },
  });

  const filtered = useMemo(
    () => (data ? filterByTypes(data, visibleTypes) : undefined),
    [data, visibleTypes],
  );

  const highlightIds = useMemo(() => {
    if (!filtered || !search.trim()) return undefined;
    const q = search.trim().toLowerCase();
    const ids = new Set(
      filtered.nodes.filter((n) => n.label.toLowerCase().includes(q)).map((n) => n.node_id),
    );
    return ids;
  }, [filtered, search]);

  function toggleType(type: NodeType) {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        if (next.size === 1) return next;
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }

  return (
    <>
      <TopBar title="Explore" subtitle="Interactive view of the semantic knowledge graph" />
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 relative min-w-0">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <Spinner size={24} />
            </div>
          )}
          {filtered && <GraphCanvas
            data={filtered}
            selectedId={selectedId}
            highlightIds={highlightIds}
            dimUnhighlighted={!!highlightIds}
            centerId={selectedId}
            onNodeClick={(node) => setSelectedId(node.node_id)}
          />}

          <div className="absolute top-4 left-4 right-4 flex items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-faint)]"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search nodes by label…"
                className="w-full glass border border-[var(--color-border)] rounded-xl pl-8 pr-3 py-2 text-xs text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] outline-none focus:border-[var(--color-accent)]/50"
              />
            </div>

            <div className="glass border border-[var(--color-border)] rounded-xl p-1 flex items-center gap-1">
              {ALL_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  className="rounded-lg"
                  style={{ opacity: visibleTypes.has(t) ? 1 : 0.35 }}
                >
                  <NodeTypeBadge type={t} className="cursor-pointer" />
                </button>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <Button
                size="sm"
                icon={<RotateCcw size={13} />}
                loading={resetMutation.isPending}
                onClick={() => resetMutation.mutate()}
              >
                Reset
              </Button>
            </div>
          </div>

          <GraphLegend />
        </div>

        <div className="w-80 shrink-0 border-l border-[var(--color-border-soft)] p-5 overflow-y-auto">
          {selectedId ? (
            <NodeDetailPanel
              detail={detailQuery.data}
              isLoading={detailQuery.isFetching}
              onSelect={setSelectedId}
              onClose={() => setSelectedId(null)}
            />
          ) : (
            <EmptyState
              icon={<Waypoints size={20} />}
              title="No node selected"
              description="Click any node in the graph to inspect its description, raw content, and relationships."
            />
          )}
        </div>
      </div>
    </>
  );
}
