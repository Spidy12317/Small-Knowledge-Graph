import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileText, GitMerge, Sparkles, Waypoints } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/Feedback";
import { Badge, NodeTypeBadge } from "../components/ui/Badge";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GraphLegend } from "../components/graph/GraphLegend";
import { api } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";
import type { CandidateResult, ParentAttachmentPlan } from "../lib/types";

// Polls the server's in-memory pipeline history so inserts made outside this
// browser tab (e.g. a notebook calling the API directly) show up here too.
const POLL_INTERVAL_MS = 4000;

const STEP_DEFS = [
  { key: "context", label: "Extract context", icon: FileText },
  { key: "locate", label: "Find insertion point", icon: Waypoints },
  { key: "attach", label: "Generate & attach", icon: GitMerge },
] as const;

type StepKey = (typeof STEP_DEFS)[number]["key"];

export function Steps() {
  const { currentGraphId } = useGraphContext();
  const { data: history } = useQuery({
    queryKey: ["pipelineHistory", currentGraphId],
    queryFn: () => api.getPipelineHistory(currentGraphId),
    enabled: !!currentGraphId,
    refetchInterval: POLL_INTERVAL_MS,
  });
  const entries = useMemo(() => history ?? [], [history]);

  // null = "follow the latest insert"; an explicit pick pins to that entry even
  // as new inserts (from this tab or elsewhere) keep arriving behind it.
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const effectiveIndex =
    selectedIndex !== null && selectedIndex < entries.length ? selectedIndex : entries.length - 1;
  const selectedInsert = entries[effectiveIndex];

  const [activeStep, setActiveStep] = useState<StepKey>("context");

  const locateHighlightIds = useMemo(() => {
    if (!selectedInsert) return undefined;
    const ids = new Set<string>();
    for (const point of selectedInsert.pipeline.insertion_points) {
      ids.add(point.node_id);
      for (const path of point.path_to_node) {
        for (const n of path) ids.add(n.node_id);
      }
    }
    return ids;
  }, [selectedInsert]);

  const attachHighlightIds = useMemo(() => {
    if (!selectedInsert) return undefined;
    const ids = new Set<string>([selectedInsert.pipeline.new_node.node_id]);
    for (const plan of selectedInsert.pipeline.parent_attachment_plans) {
      ids.add(plan.parent_id);
      for (const action of plan.actions) {
        ids.add(action.node_id);
        for (const groupedId of action.nodes_to_group) ids.add(groupedId);
      }
    }
    for (const update of selectedInsert.pipeline.parent_label_description_updates) {
      ids.add(update.node_id);
    }
    return ids;
  }, [selectedInsert]);

  return (
    <>
      <TopBar
        title="Steps"
        subtitle="Trace inserted chunks through the build pipeline"
      />
      <div className="flex-1 flex min-h-0">
        <div className="w-[420px] shrink-0 border-r border-[var(--color-border-soft)] p-6 overflow-y-auto space-y-5">
          {entries.length === 0 ? (
            <EmptyState
              icon={<Sparkles size={18} />}
              title="No inserts to trace yet"
              description="Insert a chunk (from the Build page or the API) and its pipeline steps will show up here."
            />
          ) : (
            <>
              <Card>
                <CardHeader
                  title="Timeline"
                  subtitle={`${entries.length} insert(s) this session`}
                />
                <div className="space-y-1 max-h-56 overflow-y-auto">
                  {entries.map((entry, i) => {
                    const isSelected = i === effectiveIndex;
                    return (
                      <button
                        key={`${entry.inserted_at}-${i}`}
                        onClick={() => setSelectedIndex(i)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs text-left transition-colors"
                        style={{
                          color: isSelected ? "var(--color-text)" : "var(--color-text-muted)",
                          backgroundColor: isSelected ? "var(--color-accent)14" : "transparent",
                          boxShadow: isSelected ? "inset 0 0 0 1px var(--color-accent)40" : "none",
                        }}
                      >
                        <span className="font-mono text-[10px] text-[var(--color-text-faint)] shrink-0">
                          #{i + 1}
                        </span>
                        <span className="truncate flex-1">{entry.chunk}</span>
                        <span className="text-[10px] text-[var(--color-text-faint)] shrink-0">
                          {new Date(entry.inserted_at).toLocaleTimeString()}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </Card>

              <Card>
                <CardHeader title="Chunk" />
                <p className="text-xs font-mono text-[var(--color-text-muted)] leading-relaxed max-h-28 overflow-y-auto whitespace-pre-wrap">
                  {selectedInsert.chunk}
                </p>
              </Card>

              <Card>
                <CardHeader title="Pipeline" />
                <div className="space-y-1.5">
                  {STEP_DEFS.map(({ key, label, icon: Icon }) => {
                    const active = activeStep === key;
                    return (
                      <button
                        key={key}
                        onClick={() => setActiveStep(key)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-colors"
                        style={{
                          color: active ? "var(--color-text)" : "var(--color-text-muted)",
                          backgroundColor: active ? "var(--color-accent)14" : "transparent",
                          boxShadow: active ? "inset 0 0 0 1px var(--color-accent)40" : "none",
                        }}
                      >
                        <Icon size={14} />
                        {label}
                      </button>
                    );
                  })}
                </div>
              </Card>

              {activeStep === "context" && (
                <Card>
                  <CardHeader
                    title="Extracted context"
                    subtitle="Rolling summary the LLM derived for this chunk"
                  />
                  <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">
                    {selectedInsert.pipeline.chunk_context || "(no context extracted)"}
                  </p>
                </Card>
              )}

              {activeStep === "locate" && (
                <Card>
                  <CardHeader
                    title="Candidate insertion points"
                    subtitle={`${selectedInsert.pipeline.insertion_points.length} candidate(s) found`}
                  />
                  <div className="space-y-2.5">
                    {selectedInsert.pipeline.insertion_points.map((point, i) => (
                      <CandidateCard key={point.node_id} index={i + 1} candidate={point} />
                    ))}
                  </div>
                </Card>
              )}

              {activeStep === "attach" && (
                <>
                  <Card>
                    <CardHeader title="New node" />
                    <NodeTypeBadge type="data" />
                    <p className="text-sm font-medium mt-2">
                      {selectedInsert.pipeline.new_node.label}
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1.5 leading-relaxed">
                      {selectedInsert.pipeline.new_node.description}
                    </p>
                  </Card>

                  {selectedInsert.pipeline.parent_attachment_plans.map((plan) => (
                    <AttachmentPlanCard key={plan.parent_id} plan={plan} />
                  ))}

                  {selectedInsert.pipeline.parent_label_description_updates.length > 0 && (
                    <Card>
                      <CardHeader
                        title="Updated parent nodes"
                        subtitle="Labels/descriptions refreshed to reflect new content"
                      />
                      <div className="space-y-2">
                        {selectedInsert.pipeline.parent_label_description_updates.map((u) => (
                          <div key={u.node_id} className="text-xs">
                            <p className="font-medium">{u.label}</p>
                            {u.description && (
                              <p className="text-[var(--color-text-muted)] mt-1 leading-relaxed">
                                {u.description}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                </>
              )}
            </>
          )}
        </div>

        <div className="flex-1 relative min-w-0">
          {selectedInsert && (
            <GraphCanvas
              data={selectedInsert.graph}
              highlightIds={activeStep === "locate" ? locateHighlightIds : activeStep === "attach" ? attachHighlightIds : undefined}
              dimUnhighlighted={activeStep !== "context"}
              centerId={activeStep === "attach" ? selectedInsert.pipeline.new_node.node_id : undefined}
            />
          )}
          <GraphLegend />
        </div>
      </div>
    </>
  );
}

function CandidateCard({ index, candidate }: { index: number; candidate: CandidateResult }) {
  const breadcrumb = candidate.path_to_node[0]?.map((n) => n.label) ?? [];

  return (
    <div className="rounded-xl border border-[var(--color-border)] p-3.5">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] font-mono text-[var(--color-text-faint)]">#{index}</span>
        <NodeTypeBadge type={candidate.node_type} />
      </div>
      <p className="text-sm font-medium leading-snug">{candidate.node.label}</p>
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
      {candidate.reasoning && (
        <p className="text-xs text-[var(--color-text-muted)] mt-2 leading-relaxed">
          {candidate.reasoning}
        </p>
      )}
    </div>
  );
}

function AttachmentPlanCard({ plan }: { plan: ParentAttachmentPlan }) {
  return (
    <Card>
      <CardHeader
        title="Attachment plan"
        subtitle={`Parent ${plan.parent_id.slice(0, 8)}…`}
        action={<Badge tone="accent">{plan.actions.length} action(s)</Badge>}
      />
      {plan.actions.length === 0 ? (
        <p className="text-xs text-[var(--color-text-faint)]">
          Parent had capacity — no reorganization needed.
        </p>
      ) : (
        <div className="space-y-3">
          {plan.actions.map((action) => (
            <div key={action.node_id} className="text-xs border-l-2 border-[var(--color-accent)]/40 pl-3">
              <div className="flex items-center gap-2">
                <Badge>{action.action_type}</Badge>
                <span className="font-medium">{action.label}</span>
              </div>
              {action.description && (
                <p className="text-[var(--color-text-muted)] mt-1 leading-relaxed">
                  {action.description}
                </p>
              )}
              <p className="text-[var(--color-text-faint)] mt-1">
                Grouped {action.nodes_to_group.length} node(s)
              </p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
