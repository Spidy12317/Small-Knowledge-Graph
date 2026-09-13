import type {
  GraphData,
  GraphsListResponse,
  GraphSummary,
  HealthResponse,
  InsertResponse,
  NodeDetail,
  QueryResponse,
  TraceReplayResponse,
} from "./types";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

function withGraphParam(path: string, graphId?: string | null): string {
  if (!graphId) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}graph_id=${encodeURIComponent(graphId)}`;
}

export const api = {
  health: (graphId?: string | null) =>
    request<HealthResponse>(withGraphParam("/api/health", graphId)),
  getGraph: (graphId?: string | null) =>
    request<GraphData>(withGraphParam("/api/graph", graphId)),
  getNode: (nodeId: string, graphId?: string | null) =>
    request<NodeDetail>(
      withGraphParam(`/api/graph/nodes/${encodeURIComponent(nodeId)}`, graphId),
    ),
  resetGraph: (graphId?: string | null) =>
    request<GraphData>(withGraphParam("/api/graph/reset", graphId), { method: "POST" }),
  query: (query: string, graphId?: string | null) =>
    request<QueryResponse>("/api/query", {
      method: "POST",
      body: JSON.stringify({ query, graph_id: graphId ?? null }),
    }),
  insertChunk: (chunk: string, graphId?: string | null) =>
    request<InsertResponse>("/api/build/insert", {
      method: "POST",
      body: JSON.stringify({ chunk, graph_id: graphId ?? null }),
    }),
  getPipelineHistory: (graphId?: string | null) =>
    request<InsertResponse[]>(withGraphParam("/api/build/pipeline-history", graphId)),
  getReplaySteps: (graphId?: string | null) =>
    request<TraceReplayResponse>(withGraphParam("/api/build/steps", graphId)),
  listGraphs: () => request<GraphsListResponse>("/api/graphs"),
  createGraph: (name: string) =>
    request<GraphSummary>("/api/graphs", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  deleteGraph: (graphId: string) =>
    request<{ deleted: boolean }>(`/api/graphs/${encodeURIComponent(graphId)}`, {
      method: "DELETE",
    }),
};

export { ApiError };
