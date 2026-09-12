import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  GitBranch,
  Layers,
  Link2,
  Sparkles,
  SearchCode,
  Waypoints,
} from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { Card, CardHeader } from "../components/ui/Card";
import { StatTile } from "../components/ui/StatTile";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { Spinner } from "../components/ui/Feedback";
import { api } from "../lib/api";
import { useGraphContext } from "../lib/GraphContext";

export function Dashboard() {
  const { currentGraphId } = useGraphContext();
  const { data: health } = useQuery({
    queryKey: ["health", currentGraphId],
    queryFn: () => api.health(currentGraphId),
  });
  const { data: graph, isLoading: graphLoading } = useQuery({
    queryKey: ["graph", currentGraphId],
    queryFn: () => api.getGraph(currentGraphId),
  });

  const stats = health?.stats;

  return (
    <>
      <TopBar title="Dashboard" subtitle="Overview of your semantic knowledge graph" />
      <div className="flex-1 p-8 space-y-6 overflow-y-auto">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile
            label="Total nodes"
            value={stats?.num_nodes ?? 0}
            icon={<Layers size={18} />}
            accent="#7c6cf2"
          />
          <StatTile
            label="Edges"
            value={stats?.num_edges ?? 0}
            icon={<GitBranch size={18} />}
            accent="#fbbf24"
          />
          <StatTile
            label="Data relations"
            value={stats?.num_data_relations ?? 0}
            icon={<Link2 size={18} />}
            accent="#34d1c4"
          />
          <StatTile
            label="Data nodes"
            value={stats?.by_type?.data ?? 0}
            icon={<Waypoints size={18} />}
            accent="#a78bfa"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2 !p-0 overflow-hidden">
            <div className="p-5 pb-0">
              <CardHeader
                title="Graph preview"
                subtitle="Live snapshot — open Explore for full interaction"
                action={
                  <Link
                    to="/explore"
                    className="text-xs text-[var(--color-accent)] hover:underline flex items-center gap-1"
                  >
                    Open Explore <ArrowRight size={12} />
                  </Link>
                }
              />
            </div>
            <div className="h-80 relative">
              {graphLoading || !graph ? (
                <div className="h-full flex items-center justify-center">
                  <Spinner size={22} />
                </div>
              ) : (
                <GraphCanvas data={graph} />
              )}
            </div>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader title="Quick actions" />
              <div className="space-y-2">
                <QuickAction
                  to="/build"
                  icon={<Sparkles size={15} />}
                  label="Insert a conversation chunk"
                  desc="Watch the LLM place it in the graph"
                />
                <QuickAction
                  to="/query"
                  icon={<SearchCode size={15} />}
                  label="Run a semantic query"
                  desc="LLM-guided BFS retrieval"
                />
                <QuickAction
                  to="/explore"
                  icon={<Waypoints size={15} />}
                  label="Browse the graph"
                  desc="Inspect nodes and structure"
                />
              </div>
            </Card>

            <Card>
              <CardHeader title="Providers" subtitle="Configured LLM backends" />
              <div className="space-y-2">
                {health &&
                  Object.entries(health.llm.providers_configured).map(([name, configured]) => (
                    <div key={name} className="flex items-center justify-between text-xs">
                      <span className="text-[var(--color-text-muted)] capitalize">
                        {name.replace(/_/g, " ")}
                      </span>
                      <span
                        className="flex items-center gap-1.5"
                        style={{
                          color: configured ? "var(--color-success)" : "var(--color-text-faint)",
                        }}
                      >
                        <span
                          className="h-1.5 w-1.5 rounded-full"
                          style={{
                            backgroundColor: configured
                              ? "var(--color-success)"
                              : "var(--color-text-faint)",
                          }}
                        />
                        {configured ? "Ready" : "Not set"}
                      </span>
                    </div>
                  ))}
              </div>
            </Card>
          </div>
        </div>

        <Card>
          <CardHeader title="Conversation context" subtitle="Rolling summary maintained by the graph" />
          <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">
            {graph?.context || "No context recorded yet."}
          </p>
        </Card>
      </div>
    </>
  );
}

function QuickAction({
  to,
  icon,
  label,
  desc,
}: {
  to: string;
  icon: ReactNode;
  label: string;
  desc: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-white/[0.04] transition-colors group"
    >
      <div className="h-8 w-8 rounded-lg bg-[var(--color-accent)]/12 text-[var(--color-accent)] flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs font-medium text-[var(--color-text)] truncate">{label}</div>
        <div className="text-[11px] text-[var(--color-text-faint)] truncate">{desc}</div>
      </div>
      <ArrowRight
        size={13}
        className="ml-auto shrink-0 text-[var(--color-text-faint)] opacity-0 group-hover:opacity-100 transition-opacity"
      />
    </Link>
  );
}
