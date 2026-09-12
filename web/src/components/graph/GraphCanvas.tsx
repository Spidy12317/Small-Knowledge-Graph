import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import { useContainerSize } from "../../lib/useContainerSize";
import { nodeColor, nodeRadius } from "../../lib/nodeStyle";
import type { GraphData, GraphNode } from "../../lib/types";

interface FGNode {
  id: string;
  label: string;
  node_type: GraphNode["node_type"];
  raw: GraphNode;
}

interface FGLink {
  source: string;
  target: string;
}

export interface GraphCanvasProps {
  data: GraphData;
  selectedId?: string | null;
  highlightIds?: Set<string>;
  flashIds?: Set<string>;
  dimUnhighlighted?: boolean;
  onNodeClick?: (node: GraphNode) => void;
  centerId?: string | null;
}

const BG = "#05060a";

export function GraphCanvas({
  data,
  selectedId,
  highlightIds,
  flashIds,
  dimUnhighlighted = false,
  onNodeClick,
  centerId,
}: GraphCanvasProps) {
  const { ref: containerRef, size } = useContainerSize<HTMLDivElement>();
  const fgRef = useRef<ForceGraphMethods<FGNode, FGLink> | undefined>(undefined);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const graphData = useMemo(() => {
    return {
      nodes: data.nodes.map(
        (n): FGNode => ({ id: n.node_id, label: n.label, node_type: n.node_type, raw: n }),
      ),
      links: data.edges.map(
        (e): FGLink => ({ source: e.source_id, target: e.target_id }),
      ),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  useEffect(() => {
    const MAX_ZOOM = 6;
    let clampTimer: ReturnType<typeof setTimeout> | undefined;

    const fitTimer = setTimeout(() => {
      if (graphData.nodes.length <= 1) {
        // zoomToFit degenerates on a single node (zero-size bounding box) and can
        // zoom in far enough that the node fills the entire canvas — skip it.
        fgRef.current?.centerAt(0, 0, 300);
        fgRef.current?.zoom(2.5, 300);
        return;
      }
      fgRef.current?.zoomToFit(500, 70);
      clampTimer = setTimeout(() => {
        const fg = fgRef.current as unknown as { zoom: (level?: number, ms?: number) => number };
        if (fg && typeof fg.zoom === "function" && fg.zoom() > MAX_ZOOM) {
          fg.zoom(MAX_ZOOM, 300);
        }
      }, 550);
    }, 400);

    return () => {
      clearTimeout(fitTimer);
      clearTimeout(clampTimer);
    };
  }, [graphData]);

  useEffect(() => {
    if (!centerId) return;
    const node = (fgRef.current as unknown as { graphData?: () => { nodes: (FGNode & { x?: number; y?: number })[] } })
      ?.graphData?.()
      ?.nodes.find((n) => n.id === centerId);
    if (node && typeof node.x === "number" && typeof node.y === "number") {
      fgRef.current?.centerAt(node.x, node.y, 500);
      fgRef.current?.zoom(3.2, 500);
    }
  }, [centerId]);

  const hasHighlight = !!highlightIds && highlightIds.size > 0;

  return (
    <div ref={containerRef} className="w-full h-full relative">
      {size.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={size.width}
          height={size.height}
          graphData={graphData}
          backgroundColor={BG}
          nodeRelSize={4}
          cooldownTicks={140}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.35}
          linkColor={(link) => {
            const l = link as unknown as FGLink;
            const sourceId = typeof l.source === "string" ? l.source : (l.source as unknown as FGNode).id;
            const targetId = typeof l.target === "string" ? l.target : (l.target as unknown as FGNode).id;
            const active = hasHighlight && highlightIds!.has(sourceId) && highlightIds!.has(targetId);
            if (active) return "#7c6cf2cc";
            return dimUnhighlighted && hasHighlight ? "#1e233340" : "#252a3c";
          }}
          linkWidth={(link) => {
            const l = link as unknown as FGLink;
            const sourceId = typeof l.source === "string" ? l.source : (l.source as unknown as FGNode).id;
            const targetId = typeof l.target === "string" ? l.target : (l.target as unknown as FGNode).id;
            return hasHighlight && highlightIds!.has(sourceId) && highlightIds!.has(targetId) ? 2 : 1;
          }}
          linkDirectionalParticles={(link) => {
            const l = link as unknown as FGLink;
            const sourceId = typeof l.source === "string" ? l.source : (l.source as unknown as FGNode).id;
            const targetId = typeof l.target === "string" ? l.target : (l.target as unknown as FGNode).id;
            return hasHighlight && highlightIds!.has(sourceId) && highlightIds!.has(targetId) ? 3 : 0;
          }}
          linkDirectionalParticleWidth={2.4}
          linkDirectionalParticleColor={() => "#a78bfa"}
          linkDirectionalParticleSpeed={0.006}
          onNodeClick={(node) => {
            const n = node as unknown as FGNode;
            onNodeClick?.(n.raw);
          }}
          onNodeHover={(node) => {
            const n = node as unknown as FGNode | null;
            setHoverId(n?.id ?? null);
            if (containerRef.current) {
              containerRef.current.style.cursor = n ? "pointer" : "default";
            }
          }}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const n = node as unknown as FGNode & { x: number; y: number };
            const color = nodeColor(n.node_type);
            const r = nodeRadius(n.node_type);
            const isSelected = selectedId === n.id;
            const isHighlighted = hasHighlight && highlightIds!.has(n.id);
            const isFlashing = flashIds?.has(n.id);
            const isHovered = hoverId === n.id;
            const dimmed = dimUnhighlighted && hasHighlight && !isHighlighted;

            ctx.globalAlpha = dimmed ? 0.18 : 1;

            if (isFlashing) {
              ctx.beginPath();
              ctx.arc(n.x, n.y, r + 7, 0, 2 * Math.PI);
              ctx.strokeStyle = "#4ade80aa";
              ctx.lineWidth = 2;
              ctx.stroke();
            }

            if (isHighlighted && !dimmed) {
              ctx.beginPath();
              ctx.arc(n.x, n.y, r + 4, 0, 2 * Math.PI);
              ctx.fillStyle = `${color}33`;
              ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();

            if (isSelected) {
              ctx.lineWidth = 2;
              ctx.strokeStyle = "#ffffff";
              ctx.stroke();
            }

            const showLabel =
              isSelected ||
              isHighlighted ||
              isHovered ||
              n.node_type === "central" ||
              n.node_type === "category";

            if (showLabel) {
              const fontSize = Math.max(11 / globalScale, 3.6);
              ctx.font = `${n.node_type === "central" ? 600 : 500} ${fontSize}px Inter, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = dimmed ? "#565b7360" : "#e7e9f3";
              const label =
                n.label.length > 34 ? n.label.slice(0, 32) + "…" : n.label;
              ctx.fillText(label, n.x, n.y + r + 3);
            }

            ctx.globalAlpha = 1;
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            const n = node as unknown as FGNode & { x: number; y: number };
            const r = nodeRadius(n.node_type) + 4;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
