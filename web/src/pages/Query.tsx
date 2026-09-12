import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ChevronRight, SearchCode } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorBanner, Spinner } from "../components/ui/Feedback";
import { NodeTypeBadge } from "../components/ui/Badge";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GraphLegend } from "../components/graph/GraphLegend";
import { api, ApiError } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";
import type { CandidateResult, GraphData, QueryResponse } from "../lib/types";

const EXAMPLES = [
  "What is TechNova doing with AI?",
  "Tell me about the gaming PC build",
  "What's TechNova's financial outlook?",
];

export function Query() {
  const { currentGraphId } = useGraphContext();
  const { data: graph } = useQuery({
    queryKey: ["graph", currentGraphId],
    queryFn: () => api.getGraph(currentGraphId),
    enabled: !!currentGraphId,
  });
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const mutation = useMutation<QueryResponse, ApiError, string>({
    mutationFn: (q: string) => api.query(q, currentGraphId),
    onSuccess: (res) => setSelectedId(res.results[0]?.node_id ?? null),
  });

  const highlightIds = useMemo(() => {
    if (!mutation.data) return undefined;
    const ids = new Set<string>();
    for (const r of mutation.data.results) {
      ids.add(r.node_id);
      for (const path of r.path_to_node) {
        for (const n of path) ids.add(n.node_id);
      }
    }
    return ids;
  }, [mutation.data]);

  function submit() {
    if (!query.trim()) return;
    mutation.mutate(query.trim());
  }

  return (
    <>
      <TopBar title="Query" subtitle="LLM-guided BFS retrieval across the graph" />
      <div className="flex-1 flex min-h-0">
        <div className="w-[420px] shrink-0 border-r border-[var(--color-border-soft)] p-6 overflow-y-auto space-y-4">
          <Card>
            <div className="flex items-center gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="Ask a question about the conversation…"
                className="flex-1 bg-black/30 border border-[var(--color-border)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]/50 placeholder:text-[var(--color-text-faint)]"
              />
              <Button
                variant="primary"
                icon={<SearchCode size={14} />}
                loading={mutation.isPending}
                disabled={!query.trim()}
                onClick={submit}
              >
                Search
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setQuery(ex)}
                  className="text-[11px] px-2.5 py-1 rounded-full border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/40 transition-colors"
                >
                  {ex}
                </button>
              ))}
            </div>
          </Card>

          {mutation.isPending && (
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] px-1">
              <Spinner size={14} />
              Traversing the graph with LLM guidance…
            </div>
          )}

          {mutation.isError && (
            <ErrorBanner message={mutation.error?.message ?? "Query failed."} />
          )}

          {mutation.isSuccess && mutation.data.results.length === 0 && (
            <EmptyState
              icon={<SearchCode size={18} />}
              title="No matching nodes"
              description="Try rephrasing the query or asking about a different topic covered in the graph."
            />
          )}

          <div className="space-y-2.5">
            {mutation.data?.results.map((r, i) => (
              <ResultCard
                key={r.node_id}
                index={i + 1}
                result={r}
                selected={selectedId === r.node_id}
                onClick={() => setSelectedId(r.node_id)}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 relative min-w-0">
          {graph && (
            <GraphCanvas
              data={graph as GraphData}
              selectedId={selectedId}
              highlightIds={highlightIds}
              dimUnhighlighted={!!highlightIds}
              centerId={selectedId}
              onNodeClick={(n) => setSelectedId(n.node_id)}
            />
          )}
          <GraphLegend />
        </div>
      </div>
    </>
  );
}

function ResultCard({
  index,
  result,
  selected,
  onClick,
}: {
  index: number;
  result: CandidateResult;
  selected: boolean;
  onClick: () => void;
}) {
  const breadcrumb = result.path_to_node[0]?.map((n) => n.label) ?? [];

  return (
    <motion.button
      layout
      onClick={onClick}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="w-full text-left rounded-xl border p-3.5 transition-colors"
      style={{
        borderColor: selected ? "var(--color-accent)66" : "var(--color-border)",
        backgroundColor: selected ? "var(--color-accent)0f" : "transparent",
      }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] font-mono text-[var(--color-text-faint)]">#{index}</span>
        <NodeTypeBadge type={result.node_type} />
      </div>
      <p className="text-sm font-medium leading-snug">{result.node.label}</p>

      {breadcrumb.length > 0 && (
        <div className="flex items-center flex-wrap gap-1 mt-1.5 text-[10px] text-[var(--color-text-faint)]">
          {breadcrumb.map((label, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <ChevronRight size={9} />}
              {label}
            </span>
          ))}
        </div>
      )}

      {result.reasoning && (
        <p className="text-xs text-[var(--color-text-muted)] mt-2 leading-relaxed">
          {result.reasoning}
        </p>
      )}
    </motion.button>
  );
}
