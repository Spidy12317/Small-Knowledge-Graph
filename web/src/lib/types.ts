export type NodeType = "central" | "category" | "data";

export interface GraphNode {
  node_id: string;
  label: string;
  node_type: NodeType;
  description: string | null;
  raw_text: string | null;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
}

export interface DataRelation {
  source_id: string;
  target_id: string;
}

export interface GraphData {
  graph_id: string;
  name: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  data_relations: DataRelation[];
  context: string;
  central_id: string;
}

export interface GraphSummary {
  id: string;
  name: string;
  node_count: number;
  is_default: boolean;
}

export interface GraphsListResponse {
  graphs: GraphSummary[];
  default_graph_id: string;
}

export interface NodeDetail {
  node: GraphNode;
  children: GraphNode[];
  parents: GraphNode[];
}

export interface CandidateResult {
  node_id: string;
  node: GraphNode;
  node_type: NodeType;
  reasoning: string;
  path_to_node: GraphNode[][];
}

export interface QueryResponse {
  query: string;
  results: CandidateResult[];
}

export interface InsertDiff {
  added_nodes: GraphNode[];
  removed_node_ids: string[];
  updated_nodes: GraphNode[];
  added_edges: GraphEdge[];
  removed_edges: GraphEdge[];
}

export interface AttachmentAction {
  node_id: string;
  action_type: string;
  label: string;
  description: string;
  nodes_to_group: string[];
  reasoning?: Record<string, string>;
}

export interface ParentAttachmentPlan {
  parent_id: string;
  actions: AttachmentAction[];
  new_node_attachment_point: string;
}

export interface ParentLabelDescriptionUpdate {
  node_id: string;
  label: string;
  description: string | null;
}

export interface InsertPipeline {
  chunk_context: string;
  insertion_points: CandidateResult[];
  new_node: GraphNode;
  parent_attachment_plans: ParentAttachmentPlan[];
  parent_label_description_updates: ParentLabelDescriptionUpdate[];
}

export interface InsertResponse {
  chunk: string;
  inserted_at: string;
  graph: GraphData;
  diff: InsertDiff;
  pipeline: InsertPipeline;
}

export interface HealthResponse {
  status: string;
  llm: {
    provider: string;
    model: string;
    providers_configured: Record<string, boolean>;
  };
  graph_settings: {
    max_root_children: number;
    max_node_children: number;
    max_concurrent_evaluations: number;
    high_confidence_score_threshold: number;
    max_concurrent_insertions: number;
  };
  stats: {
    num_nodes: number;
    num_edges: number;
    num_data_relations: number;
    by_type: Record<string, number>;
  };
}
