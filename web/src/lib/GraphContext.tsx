import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { GraphSummary } from "./types";

const STORAGE_KEY = "skg.currentGraphId";

interface GraphContextValue {
  currentGraphId: string | null;
  currentGraph: GraphSummary | undefined;
  graphs: GraphSummary[];
  defaultGraphId: string | null;
  isLoading: boolean;
  selectGraph: (graphId: string) => void;
}

const GraphContext = createContext<GraphContextValue | undefined>(undefined);

export function GraphProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["graphs"],
    queryFn: api.listGraphs,
    refetchInterval: 30_000,
  });

  const [selectedGraphId, setSelectedGraphId] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEY),
  );

  const graphs = useMemo(() => data?.graphs ?? [], [data]);
  const defaultGraphId = data?.default_graph_id ?? null;

  // Once the list loads, fall back to the default graph if nothing was
  // stored yet, or if the stored id no longer refers to a real graph.
  useEffect(() => {
    if (!data) return;
    const stillExists = graphs.some((g) => g.id === selectedGraphId);
    if (!selectedGraphId || !stillExists) {
      setSelectedGraphId(defaultGraphId);
    }
  }, [data, graphs, selectedGraphId, defaultGraphId]);

  function selectGraph(graphId: string) {
    setSelectedGraphId(graphId);
    localStorage.setItem(STORAGE_KEY, graphId);
  }

  async function createAndSelect(name: string) {
    const created = await api.createGraph(name);
    await queryClient.invalidateQueries({ queryKey: ["graphs"] });
    selectGraph(created.id);
    return created;
  }

  const value: GraphContextValue & { createAndSelect: typeof createAndSelect } = {
    currentGraphId: selectedGraphId,
    currentGraph: graphs.find((g) => g.id === selectedGraphId),
    graphs,
    defaultGraphId,
    isLoading,
    selectGraph,
    createAndSelect,
  };

  return <GraphContext.Provider value={value}>{children}</GraphContext.Provider>;
}

export function useGraphContext() {
  const ctx = useContext(GraphContext);
  if (!ctx) throw new Error("useGraphContext must be used within a GraphProvider");
  return ctx as GraphContextValue & { createAndSelect: (name: string) => Promise<GraphSummary> };
}
