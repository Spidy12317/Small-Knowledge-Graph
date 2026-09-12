import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, Plus, Sparkles, Wand2 } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { Card, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { ErrorBanner } from "../components/ui/Feedback";
import { Badge, NodeTypeBadge } from "../components/ui/Badge";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GraphLegend } from "../components/graph/GraphLegend";
import { api, ApiError } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";
import type { GraphData, InsertResponse } from "../lib/types";

const STAGES = [
  "Extracting chunk context",
  "Searching for the best insertion point",
  "Generating node & attaching to graph",
];

const SAMPLE_CHUNKS = [
  {
    title: "ESG & sustainability",
    text: '((\'Sara\', \'Did TechNova say anything about sustainability or ESG goals?\'), (\'Alex\', "Yeah, actually. They committed to net-zero emissions by 2030 and announced a $50 million green data center initiative in partnership with a renewable energy provider."))',
  },
  {
    title: "Unrelated topic switch",
    text: "((\'Sara\', \'Totally different question — did you catch the new season of that sci-fi show?\'), (\'Alex\', \"Yeah, just finished it. The finale twist was wild, definitely setting up for another season.\"))",
  },
];

function NewGraphCard() {
  const { currentGraph, createAndSelect } = useGraphContext();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      await createAndSelect(trimmed);
      setName("");
      setCreating(false);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create graph");
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">
            Building on
          </p>
          <p className="text-sm font-medium truncate">{currentGraph?.name ?? "—"}</p>
        </div>
        <Badge>{currentGraph?.node_count ?? 0} nodes</Badge>
      </div>

      {creating ? (
        <div className="mt-3 space-y-2">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder="New graph name…"
            className="w-full bg-black/30 border border-[var(--color-border)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--color-accent)]/50 placeholder:text-[var(--color-text-faint)]"
          />
          {error && <p className="text-[10px] text-[var(--color-danger)]">{error}</p>}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="primary"
              className="flex-1"
              disabled={!name.trim()}
              onClick={handleCreate}
            >
              Create empty graph
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setCreating(false);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setCreating(true)}
          className="mt-3 w-full flex items-center justify-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] border border-dashed border-[var(--color-border)] hover:border-[var(--color-accent)]/40 rounded-lg py-2 transition-colors"
        >
          <Plus size={13} />
          Start a new graph from scratch
        </button>
      )}
    </Card>
  );
}

export function Build() {
  const queryClient = useQueryClient();
  const { currentGraphId } = useGraphContext();
  const { data: graph } = useQuery({
    queryKey: ["graph", currentGraphId],
    queryFn: () => api.getGraph(currentGraphId),
    enabled: !!currentGraphId,
  });

  const [chunk, setChunk] = useState("");
  const [stage, setStage] = useState(0);
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set());
  const [centerId, setCenterId] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const mutation = useMutation<InsertResponse, ApiError, string>({
    mutationFn: (c: string) => api.insertChunk(c, currentGraphId),
    onMutate: () => {
      setStage(0);
      setFlashIds(new Set());
      timers.current.push(setTimeout(() => setStage(1), 2800));
      timers.current.push(setTimeout(() => setStage(2), 6500));
    },
    onSuccess: (res) => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
      setStage(3);
      queryClient.setQueryData(["graph", currentGraphId], res.graph);
      queryClient.invalidateQueries({ queryKey: ["graphs"] });
      queryClient.setQueryData(
        ["pipelineHistory", currentGraphId],
        (history: InsertResponse[] | undefined) => [...(history ?? []), res],
      );
      const ids = new Set([
        ...res.diff.added_nodes.map((n) => n.node_id),
        ...res.diff.updated_nodes.map((n) => n.node_id),
      ]);
      setFlashIds(ids);
      const newData = res.diff.added_nodes.find((n) => n.node_type === "data");
      if (newData) setCenterId(newData.node_id);
      setTimeout(() => setFlashIds(new Set()), 5000);
    },
    onError: () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
    },
  });

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const newDataNode = mutation.data?.diff.added_nodes.find((n) => n.node_type === "data");
  const newCategories = mutation.data?.diff.added_nodes.filter((n) => n.node_type === "category") ?? [];
  const updatedParents = mutation.data?.diff.updated_nodes ?? [];

  return (
    <>
      <TopBar title="Build" subtitle="Insert a new conversation chunk and watch it join the graph" />
      <div className="flex-1 flex min-h-0">
        <div className="w-[420px] shrink-0 border-r border-[var(--color-border-soft)] p-6 overflow-y-auto space-y-5">
          <NewGraphCard />

          <Card>
            <CardHeader title="New chunk" subtitle="Paste conversation text or notes to insert" />
            <textarea
              value={chunk}
              onChange={(e) => setChunk(e.target.value)}
              placeholder="e.g. a snippet of conversation, a note, or any piece of text…"
              rows={7}
              className="w-full resize-none rounded-xl bg-black/30 border border-[var(--color-border)] p-3 text-xs font-mono text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] outline-none focus:border-[var(--color-accent)]/50"
            />
            <div className="flex flex-wrap gap-2 mt-3">
              {SAMPLE_CHUNKS.map((s) => (
                <button
                  key={s.title}
                  onClick={() => setChunk(s.text)}
                  className="text-[11px] px-2.5 py-1 rounded-full border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/40 transition-colors"
                >
                  {s.title}
                </button>
              ))}
            </div>
            <Button
              variant="primary"
              className="w-full mt-4"
              icon={<Wand2 size={14} />}
              loading={mutation.isPending}
              disabled={!chunk.trim()}
              onClick={() => mutation.mutate(chunk)}
            >
              Insert into graph
            </Button>
          </Card>

          {(mutation.isPending || mutation.isSuccess) && (
            <Card>
              <CardHeader title="Pipeline" />
              <div className="space-y-3">
                {STAGES.map((label, i) => {
                  const done = stage > i || mutation.isSuccess;
                  const active = stage === i && mutation.isPending;
                  return (
                    <div key={label} className="flex items-center gap-3 text-xs">
                      <div
                        className="h-5 w-5 rounded-full flex items-center justify-center shrink-0 border"
                        style={{
                          borderColor: done
                            ? "var(--color-success)"
                            : active
                              ? "var(--color-accent)"
                              : "var(--color-border)",
                          color: done ? "var(--color-success)" : "var(--color-accent)",
                        }}
                      >
                        {done ? (
                          <Check size={12} />
                        ) : active ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : null}
                      </div>
                      <span
                        className={
                          done || active
                            ? "text-[var(--color-text)]"
                            : "text-[var(--color-text-faint)]"
                        }
                      >
                        {label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {mutation.isError && (
            <ErrorBanner
              message={mutation.error?.message ?? "Something went wrong while inserting the chunk."}
            />
          )}

          <AnimatePresence>
            {mutation.isSuccess && newDataNode && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <Card>
                  <CardHeader title="New node created" />
                  <NodeTypeBadge type="data" />
                  <p className="text-sm font-medium mt-2">{newDataNode.label}</p>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1.5 leading-relaxed">
                    {newDataNode.description}
                  </p>
                </Card>

                {newCategories.length > 0 && (
                  <Card>
                    <CardHeader
                      title="New categories"
                      subtitle="Created to reorganize a full parent"
                    />
                    <div className="space-y-2">
                      {newCategories.map((c) => (
                        <div key={c.node_id} className="text-xs">
                          <NodeTypeBadge type="category" />
                          <p className="font-medium mt-1">{c.label}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {updatedParents.length > 0 && (
                  <Card>
                    <CardHeader
                      title="Updated parent nodes"
                      subtitle="Labels/descriptions refreshed to reflect new content"
                    />
                    <div className="space-y-2">
                      {updatedParents.map((p) => (
                        <div key={p.node_id} className="text-xs">
                          <NodeTypeBadge type={p.node_type} />
                          <p className="font-medium mt-1">{p.label}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex-1 relative min-w-0">
          {graph && (
            <GraphCanvas
              data={graph as GraphData}
              flashIds={flashIds}
              centerId={centerId}
              highlightIds={flashIds.size ? flashIds : undefined}
              dimUnhighlighted={flashIds.size > 0}
            />
          )}
          {!mutation.isSuccess && !mutation.isPending && (
            <div className="absolute top-4 left-4 glass border border-[var(--color-border)] rounded-xl px-3.5 py-2.5 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
              <Sparkles size={13} className="text-[var(--color-accent)]" />
              Insert a chunk to see it land in the graph
            </div>
          )}
          <GraphLegend />
        </div>
      </div>
    </>
  );
}
