import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, FolderOpen } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GraphLegend } from "../components/graph/GraphLegend";
import { Button } from "../components/ui/Button";
import { EmptyState, Spinner } from "../components/ui/Feedback";
import { api } from "../lib/api";
import type { GraphData } from "../lib/types";

export function CheckpointReplay() {
  const [folderIds, setFolderIds] = useState<string[]>([]);
  const [graphId, setGraphId] = useState("");
  const [steps, setSteps] = useState<number[]>([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listCheckpointFolders().then(setFolderIds).catch(() => setFolderIds([]));
  }, []);

  const currentStep = steps[stepIndex] ?? null;

  const loadStep = useCallback(async (gid: string, step: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCheckpointGraph(gid, step);
      setGraph(data);
    } catch (e) {
      setGraph(null);
      setError(e instanceof Error ? e.message : "Failed to load checkpoint");
    } finally {
      setLoading(false);
    }
  }, []);

  async function openFolder() {
    const gid = graphId.trim();
    if (!gid) {
      setError("Enter a graph folder id (UUID under data/)");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { steps: listed } = await api.listCheckpointSteps(gid);
      setSteps(listed);
      setStepIndex(0);
      await loadStep(gid, listed[0]);
    } catch (e) {
      setSteps([]);
      setGraph(null);
      setError(e instanceof Error ? e.message : "Failed to list checkpoints");
    } finally {
      setLoading(false);
    }
  }

  function goNext() {
    if (stepIndex >= steps.length - 1) return;
    const next = stepIndex + 1;
    setStepIndex(next);
    loadStep(graphId.trim(), steps[next]);
  }

  function goPrev() {
    if (stepIndex <= 0) return;
    const prev = stepIndex - 1;
    setStepIndex(prev);
    loadStep(graphId.trim(), steps[prev]);
  }

  return (
    <>
      <TopBar
        title="Checkpoint replay"
        subtitle="Step through saved graph snapshots in data/{graph-id}/"
      />
      <div className="flex-1 flex flex-col min-h-0 p-6 gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-[var(--color-text-muted)]">Graph folder (UUID)</span>
            <input
              list="checkpoint-folders"
              value={graphId}
              onChange={(e) => setGraphId(e.target.value)}
              placeholder="e.g. 3fa85f64-..."
              className="w-80 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border-soft)] text-sm"
            />
            <datalist id="checkpoint-folders">
              {folderIds.map((id) => (
                <option key={id} value={id} />
              ))}
            </datalist>
          </label>
          <Button onClick={openFolder} disabled={loading}>
            <FolderOpen size={16} />
            Open
          </Button>
          {steps.length > 0 && currentStep !== null && (
            <div className="flex items-center gap-2 ml-auto">
              <Button variant="secondary" onClick={goPrev} disabled={stepIndex === 0 || loading}>
                <ChevronLeft size={16} />
                Previous
              </Button>
              <span className="text-sm text-[var(--color-text-muted)] tabular-nums min-w-[8rem] text-center">
                Step {currentStep} ({stepIndex + 1} / {steps.length})
              </span>
              <Button
                variant="secondary"
                onClick={goNext}
                disabled={stepIndex >= steps.length - 1 || loading}
              >
                Next
                <ChevronRight size={16} />
              </Button>
            </div>
          )}
        </div>

        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}

        <div className="flex-1 min-h-[420px] rounded-2xl border border-[var(--color-border-soft)] overflow-hidden relative bg-[#05060a]">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center z-10 bg-black/40">
              <Spinner />
            </div>
          )}
          {graph ? (
            <GraphCanvas data={graph} />
          ) : (
            !loading && (
              <EmptyState
                icon={<FolderOpen size={18} />}
                title="No checkpoint loaded"
                description="Pick the graph id folder name from data/, then Open to view step 1."
              />
            )
          )}
        </div>
        <GraphLegend />
      </div>
    </>
  );
}
