import { useQuery } from "@tanstack/react-query";
import { Cpu, Gauge, ShieldCheck } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { Card, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Feedback";
import { api } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";

export function Settings() {
  const { currentGraphId } = useGraphContext();
  const { data, isLoading } = useQuery({
    queryKey: ["health", currentGraphId],
    queryFn: () => api.health(currentGraphId),
  });

  if (isLoading || !data) {
    return (
      <>
        <TopBar title="Settings" subtitle="Runtime configuration" />
        <div className="flex-1 flex items-center justify-center">
          <Spinner size={22} />
        </div>
      </>
    );
  }

  const graphSettings: [string, number][] = [
    ["Max root children", data.graph_settings.max_root_children],
    ["Max node children", data.graph_settings.max_node_children],
    ["Max concurrent evaluations", data.graph_settings.max_concurrent_evaluations],
    ["Max concurrent insertions", data.graph_settings.max_concurrent_insertions],
    ["High-confidence threshold", data.graph_settings.high_confidence_score_threshold],
  ];

  return (
    <>
      <TopBar title="Settings" subtitle="Runtime configuration for the graph & LLM engine" />
      <div className="flex-1 p-8 space-y-6 overflow-y-auto max-w-4xl">
        <Card>
          <CardHeader title="Active model" subtitle="Used for insertion and retrieval reasoning" />
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-[var(--color-accent)]/12 text-[var(--color-accent)] flex items-center justify-center">
              <Cpu size={18} />
            </div>
            <div>
              <p className="text-sm font-medium capitalize">{data.llm.provider.replace(/_/g, " ")}</p>
              <p className="text-xs font-mono text-[var(--color-text-muted)]">{data.llm.model}</p>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Providers"
            subtitle="Configured via environment variables (.env) — restart the API to apply changes"
          />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {Object.entries(data.llm.providers_configured).map(([name, configured]) => (
              <div
                key={name}
                className="rounded-xl border border-[var(--color-border)] px-3.5 py-3 flex items-center justify-between"
              >
                <span className="text-xs capitalize text-[var(--color-text-muted)]">
                  {name.replace(/_/g, " ")}
                </span>
                <Badge tone={configured ? "success" : "neutral"}>
                  {configured ? "Configured" : "Unset"}
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Graph tuning"
            subtitle="Controls how the hierarchy grows and how retrieval traverses it"
          />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {graphSettings.map(([label, value]) => (
              <div key={label}>
                <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-[var(--color-text-faint)] mb-1">
                  <Gauge size={11} />
                  {label}
                </div>
                <div className="text-lg font-semibold tabular-nums">{value}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="About this build" />
          <div className="flex items-start gap-3 text-xs text-[var(--color-text-muted)] leading-relaxed">
            <ShieldCheck size={16} className="text-[var(--color-success)] shrink-0 mt-0.5" />
            <p>
              This UI talks to a local FastAPI service backed by Postgres — insertions and
              queries make real calls to the configured provider, and every mutation is
              committed immediately. Use Reset on the Explore page to wipe the graph and
              reseed it from the bundled sample conversation.
            </p>
          </div>
        </Card>
      </div>
    </>
  );
}
