import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { Card, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { EmptyState, Spinner } from "../components/ui/Feedback";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GraphLegend } from "../components/graph/GraphLegend";
import { api } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";
import type { TraceLlmCall, TraceReplayStep } from "../lib/types";

const POLL_INTERVAL_MS = 5000;

export function Steps() {
  const { currentGraphId } = useGraphContext();
  const { data, isLoading } = useQuery({
    queryKey: ["replaySteps", currentGraphId],
    queryFn: () => api.getReplaySteps(currentGraphId),
    enabled: !!currentGraphId,
    refetchInterval: POLL_INTERVAL_MS,
  });
  const steps = useMemo(() => data?.steps ?? [], [data]);

  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const effectiveIndex =
    selectedIndex !== null && selectedIndex < steps.length ? selectedIndex : steps.length - 1;
  const selected = steps[effectiveIndex];

  const highlightIds = useMemo(() => {
    if (!selected) return undefined;
    return new Set(selected.added_node_ids);
  }, [selected]);

  return (
    <>
      <TopBar
        title="Steps"
        subtitle="Replay recorded decisions for the selected graph. The stored graph is not modified."
      />
      <div className="flex-1 flex min-h-0">
        <div className="w-[460px] shrink-0 border-r border-[var(--color-border-soft)] p-6 overflow-y-auto space-y-5">
          {isLoading ? (
            <div className="flex justify-center py-16">
              <Spinner />
            </div>
          ) : steps.length === 0 ? (
            <EmptyState
              icon={<Sparkles size={18} />}
              title="No traced steps yet"
              description="Insert a chunk with tracing started and each graph update will show up here."
            />
          ) : (
            <>
              <Card>
                <CardHeader
                  title="Timeline"
                  subtitle={`${steps.length} step(s) · showing the graph through step ${selected.index}`}
                />
                <div className="space-y-1 max-h-56 overflow-y-auto">
                  {steps.map((step, i) => (
                    <TimelineRow
                      key={step.trace_id}
                      step={step}
                      selected={i === effectiveIndex}
                      onSelect={() => setSelectedIndex(i)}
                    />
                  ))}
                </div>
              </Card>

              <Card>
                <CardHeader title={`Step ${selected.index}`} subtitle={selected.trace_id} />
                <p className="text-xs font-mono text-[var(--color-text-muted)] leading-relaxed max-h-28 overflow-y-auto whitespace-pre-wrap">
                  {selected.chunk || "(no chunk recorded)"}
                </p>
                {selected.chunk_context && (
                  <p className="text-xs text-[var(--color-text-muted)] leading-relaxed mt-3">
                    {selected.chunk_context}
                  </p>
                )}
              </Card>

              <Card>
                <CardHeader title="Decisions" subtitle="In the order they ran" />
                <div className="space-y-1">
                  {selected.spans.map((span) => (
                    <div
                      key={`${span.step_index}-${span.name}`}
                      className="flex items-center gap-2 text-xs py-1"
                    >
                      <span className="font-mono text-[10px] text-[var(--color-text-faint)] w-6">
                        {span.step_index}
                      </span>
                      <span className="flex-1 truncate text-[var(--color-text-muted)]">{span.name}</span>
                      {span.status === "ERROR" && <Badge tone="danger">error</Badge>}
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <CardHeader
                  title="Model calls"
                  subtitle={`${selected.llm_calls.length} call(s) · input and output`}
                />
                <div className="space-y-2">
                  {selected.llm_calls.map((call, i) => (
                    <LlmCallCard key={`${call.step_index}-${i}`} index={i + 1} call={call} />
                  ))}
                </div>
              </Card>
            </>
          )}
        </div>

        <div className="flex-1 relative min-w-0">
          {selected && (
            <GraphCanvas
              data={selected.graph}
              highlightIds={highlightIds}
              dimUnhighlighted={selected.added_node_ids.length > 0}
              centerId={selected.added_node_ids[0]}
            />
          )}
          <GraphLegend />
        </div>
      </div>
    </>
  );
}

function TimelineRow({
  step,
  selected,
  onSelect,
}: {
  step: TraceReplayStep;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs text-left transition-colors"
      style={{
        color: selected ? "var(--color-text)" : "var(--color-text-muted)",
        backgroundColor: selected ? "var(--color-accent)14" : "transparent",
        boxShadow: selected ? "inset 0 0 0 1px var(--color-accent)40" : "none",
      }}
    >
      <span className="font-mono text-[10px] text-[var(--color-text-faint)] shrink-0">
        #{step.index}
      </span>
      <span className="truncate flex-1">{step.chunk}</span>
      <span className="text-[10px] text-[var(--color-text-faint)] shrink-0">
        {new Date(step.started_at).toLocaleTimeString()}
      </span>
    </button>
  );
}

function LlmCallCard({ index, call }: { index: number; call: TraceLlmCall }) {
  const preview = reasoningPreview(call.output);
  return (
    <details className="rounded-xl border border-[var(--color-border)] px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium list-none flex items-center gap-2">
        <span className="font-mono text-[10px] text-[var(--color-text-faint)]">#{index}</span>
        <span>LLM call</span>
        {call.status === "ERROR" && <Badge tone="danger">error</Badge>}
      </summary>
      {preview && (
        <p className="text-xs text-[var(--color-text-muted)] mt-2 leading-relaxed">{preview}</p>
      )}
      <PromptBlock label="System" text={call.system} />
      <PromptBlock label="User" text={call.user} />
      <PromptBlock label="Output" text={formatOutput(call.output)} />
    </details>
  );
}

function PromptBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="mt-3">
      <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)] mb-1">{label}</p>
      <pre className="text-[11px] font-mono text-[var(--color-text-muted)] leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
        {text || "(empty)"}
      </pre>
    </div>
  );
}

function formatOutput(output: unknown): string {
  if (output == null) return "";
  if (typeof output === "string") return output;
  return JSON.stringify(output, null, 2);
}

function reasoningPreview(output: unknown): string {
  const found: string[] = [];
  collectReasoning(output, found);
  return found[0] ?? "";
}

function collectReasoning(value: unknown, found: string[]) {
  if (found.length > 0 || value == null) return;
  if (typeof value === "string") return;
  if (Array.isArray(value)) {
    for (const item of value) collectReasoning(item, found);
    return;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const reason = record.reasoning;
    if (typeof reason === "string" && reason.trim()) {
      found.push(reason);
      return;
    }
    for (const item of Object.values(record)) collectReasoning(item, found);
  }
}
