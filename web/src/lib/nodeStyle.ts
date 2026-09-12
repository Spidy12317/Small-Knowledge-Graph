import type { NodeType } from "./types";

export const NODE_COLORS: Record<NodeType, string> = {
  central: "#a78bfa",
  category: "#fbbf24",
  data: "#34d1c4",
};

export const NODE_LABELS: Record<NodeType, string> = {
  central: "Central",
  category: "Category",
  data: "Data",
};

export function nodeColor(type: NodeType): string {
  return NODE_COLORS[type] ?? "#8b90a8";
}

export function nodeRadius(type: NodeType): number {
  if (type === "central") return 10;
  if (type === "category") return 7;
  return 4.5;
}
