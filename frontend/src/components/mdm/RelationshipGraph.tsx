"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationNodeDatum,
} from "d3-force";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/api";
import { domainNodeFill } from "./Badges";
import { GraphNodeDetail } from "./GraphNodeDetail";

type SimNode = GraphNode & SimulationNodeDatum;
type SimLink = {
  source: SimNode | number;
  target: SimNode | number;
  type: string;
  properties: Record<string, unknown>;
};

const DEFAULT_WIDTH = 900;
const DEFAULT_HEIGHT = 560;
const CLICK_DRAG_THRESHOLD = 4;
const LABEL_MAX_CHARS = 24;

function truncate(name: string | null): string {
  if (!name) return "—";
  return name.length > LABEL_MAX_CHARS ? `${name.slice(0, LABEL_MAX_CHARS - 1)}…` : name;
}

// Generic fallback (works for any relationship type a client's own data might
// use), humanizing whatever type string is present.
function baseLabel(type: string): string {
  if (type === "OWNS") return "Owns";
  const words = type.split("_").filter(Boolean);
  return words.map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}

// Full detail including GLEIF's direct-vs-ultimate-parent distinction, used
// for per-edge labels — kept separate from baseLabel() so the "is this graph
// uniform" check below can group by type alone (a company's ownership chain
// is almost always a mix of direct/ultimate, which would otherwise defeat
// the grouping) while hover still reveals the precise distinction.
function edgeLabel(link: SimLink): string {
  if (link.type === "OWNS") {
    const direct = Boolean(link.properties?.is_direct_parent);
    const ultimate = Boolean(link.properties?.is_ultimate_parent);
    if (direct && ultimate) return "Owns (direct & ultimate)";
    if (direct) return "Owns (direct)";
    if (ultimate) return "Owns (ultimate)";
  }
  return baseLabel(link.type);
}

function nodeRadius(node: GraphNode): number {
  if (node.is_anchor) return 20;
  if (node.existing_customer) return 16;
  return 13;
}

function asNode(end: SimNode | number): SimNode | null {
  return typeof end === "object" ? end : null;
}

// Lines used to run straight into the target node's center, so the
// arrowhead marker landed underneath the node circle (drawn on top) and was
// invisible. Pull the line's end back to just outside the target's edge.
function edgeEndpoint(source: SimNode, target: SimNode): { x: number; y: number } {
  const sx = source.x ?? 0;
  const sy = source.y ?? 0;
  const tx = target.x ?? 0;
  const ty = target.y ?? 0;
  const dx = tx - sx;
  const dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const r = nodeRadius(target) + 3;
  return { x: tx - (dx / dist) * r, y: ty - (dy / dist) * r };
}

interface Props {
  data: GraphResponse;
  onRecenter: (id: number) => void;
}

export function RelationshipGraph({ data, onRecenter }: Props) {
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [links, setLinks] = useState<SimLink[]>([]);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [size, setSize] = useState({ width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT });

  const containerRef = useRef<HTMLDivElement | null>(null);
  const simulationRef = useRef<Simulation<SimNode, undefined> | null>(null);
  const draggingRef = useRef<{ id: number; moved: boolean; startX: number; startY: number } | null>(null);
  const panningRef = useRef<{ startX: number; startY: number; origin: { x: number; y: number }; moved: boolean } | null>(
    null
  );

  // The graph fills whatever space its container actually has (a fixed
  // viewBox just letterboxed instead of using the extra room fullscreen
  // mode opens up — the whole point of fullscreen for a big, congested
  // graph is to spread nodes across more space, not just cover the sidebar).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setSize({ width: Math.round(width), height: Math.round(height) });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setSelectedId(null);
  }, [data]);

  useEffect(() => {
    const simNodes: SimNode[] = data.nodes.map((n) => ({
      ...n,
      x: size.width / 2 + (Math.random() - 0.5) * 60,
      y: size.height / 2 + (Math.random() - 0.5) * 60,
    }));
    const simLinks: SimLink[] = data.edges.map((e: GraphEdge) => ({
      source: e.source,
      target: e.target,
      type: e.type,
      properties: e.properties,
    }));

    // Bigger graphs need proportionally more room, or a high-fan-out anchor
    // (a real company can have 50+ direct subsidiaries) turns into an
    // unreadable ball of overlapping labels. Scale spacing with node count,
    // capped so it doesn't get absurd for very large graphs.
    const n = simNodes.length;
    const linkDistance = Math.min(200, 90 + n * 2);
    const chargeStrength = Math.max(-650, -220 - n * 8);

    const simulation = forceSimulation(simNodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(linkDistance)
          .strength(0.45)
      )
      .force("charge", forceManyBody().strength(chargeStrength))
      .force("center", forceCenter(size.width / 2, size.height / 2))
      .force("collide", forceCollide<SimNode>().radius((d) => nodeRadius(d) + 18))
      .on("tick", () => {
        setNodes([...simNodes]);
        setLinks([...simLinks]);
      });

    simulationRef.current = simulation;

    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // Re-center (not re-layout from scratch) when the container is resized —
  // e.g. entering/exiting fullscreen — so nodes drift to use the new space
  // instead of staying clustered around the old, smaller center.
  useEffect(() => {
    const simulation = simulationRef.current;
    if (!simulation) return;
    simulation.force("center", forceCenter(size.width / 2, size.height / 2));
    simulation.alpha(0.4).restart();
  }, [size.width, size.height]);

  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  // A hub anchor (a real company can have 50+ direct subsidiaries) makes
  // "always show the anchor's own edges" pointless — nearly every edge
  // touches the anchor, so that rule alone doesn't declutter anything. Group
  // by relationship *type* rather than the full label: an ownership chain is
  // almost always a mix of direct/ultimate parents, which would otherwise
  // never register as "uniform" even though every edge is still just OWNS.
  // When every edge is the same type, one legend line says it once instead
  // of repeating near-identical text 50 times; hover reveals the precise
  // direct/ultimate detail per edge.
  const distinctTypes = useMemo(() => new Set(links.map((l) => l.type)), [links]);
  const isUniform = links.length > 0 && distinctTypes.size === 1;
  const isDense = links.length > 15;

  // Degree within *this* view only (the loaded hop radius), not the
  // record's true total connection count — cheap client-side count over
  // edges already on hand, no extra request.
  const degreeById = useMemo(() => {
    const counts = new Map<number, number>();
    for (const link of links) {
      const s = asNode(link.source)?.id ?? (typeof link.source === "number" ? link.source : null);
      const t = asNode(link.target)?.id ?? (typeof link.target === "number" ? link.target : null);
      if (s != null) counts.set(s, (counts.get(s) ?? 0) + 1);
      if (t != null) counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return counts;
  }, [links]);

  const selectedNode = useMemo(
    () => (selectedId != null ? (data.nodes.find((n) => n.id === selectedId) ?? null) : null),
    [selectedId, data.nodes]
  );
  const domainsPresent = useMemo(
    () => Array.from(new Set(data.nodes.map((n) => n.domain).filter((d): d is string => Boolean(d)))),
    [data.nodes]
  );

  // Dimming shows the selected node's immediate neighborhood, not just the
  // node itself — matching how the amber "existing customer" callout etc.
  // already reads relationships one hop at a time.
  const selectionNeighborhood = useMemo(() => {
    if (selectedId == null) return null;
    const ids = new Set<number>([selectedId]);
    for (const link of links) {
      const s = asNode(link.source)?.id;
      const t = asNode(link.target)?.id;
      if (s === selectedId && t != null) ids.add(t);
      if (t === selectedId && s != null) ids.add(s);
    }
    return ids;
  }, [selectedId, links]);

  const nodeTouchesSelection = (id: number) => selectionNeighborhood == null || selectionNeighborhood.has(id);
  const linkTouchesSelection = (link: SimLink) => {
    if (selectedId == null) return true;
    const s = asNode(link.source)?.id;
    const t = asNode(link.target)?.id;
    return s === selectedId || t === selectedId;
  };

  const toGraphCoords = (clientX: number, clientY: number, svg: SVGSVGElement) => {
    const rect = svg.getBoundingClientRect();
    return {
      x: (clientX - rect.left - transform.x) / transform.k,
      y: (clientY - rect.top - transform.y) / transform.k,
    };
  };

  const handleNodePointerDown = (e: React.PointerEvent<SVGGElement>, node: SimNode) => {
    e.stopPropagation();
    (e.target as Element).setPointerCapture(e.pointerId);
    draggingRef.current = { id: node.id, moved: false, startX: e.clientX, startY: e.clientY };
    node.fx = node.x;
    node.fy = node.y;
    simulationRef.current?.alphaTarget(0.25).restart();
  };

  const handleSvgPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const dragging = draggingRef.current;
    if (dragging) {
      const dx = e.clientX - dragging.startX;
      const dy = e.clientY - dragging.startY;
      if (Math.abs(dx) > CLICK_DRAG_THRESHOLD || Math.abs(dy) > CLICK_DRAG_THRESHOLD) dragging.moved = true;
      const node = nodesById.get(dragging.id);
      if (node) {
        const { x, y } = toGraphCoords(e.clientX, e.clientY, e.currentTarget);
        node.fx = x;
        node.fy = y;
      }
      return;
    }
    const panning = panningRef.current;
    if (panning) {
      const dx = e.clientX - panning.startX;
      const dy = e.clientY - panning.startY;
      if (Math.abs(dx) > CLICK_DRAG_THRESHOLD || Math.abs(dy) > CLICK_DRAG_THRESHOLD) panning.moved = true;
      setTransform((prev) => ({
        ...prev,
        x: panning.origin.x + dx,
        y: panning.origin.y + dy,
      }));
    }
  };

  const handleNodePointerUp = (e: React.PointerEvent<SVGGElement>, node: SimNode) => {
    const dragging = draggingRef.current;
    draggingRef.current = null;
    simulationRef.current?.alphaTarget(0);
    node.fx = null;
    node.fy = null;
    if (dragging && !dragging.moved) {
      setSelectedId((prev) => (prev === node.id ? null : node.id));
    }
  };

  const handleBackgroundPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    (e.target as Element).setPointerCapture(e.pointerId);
    panningRef.current = { startX: e.clientX, startY: e.clientY, origin: { x: transform.x, y: transform.y }, moved: false };
  };

  const handleBackgroundPointerUp = () => {
    const panning = panningRef.current;
    panningRef.current = null;
    if (panning && !panning.moved) setSelectedId(null);
  };

  const handleWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform((prev) => {
      const k = Math.min(2.5, Math.max(0.3, prev.k * factor));
      return { ...prev, k };
    });
  };

  return (
    <div className="flex h-full w-full gap-3">
      <div ref={containerRef} className="relative h-full min-w-0 flex-1">
      <div className="pointer-events-none absolute left-3 top-3 z-10 flex flex-col gap-1.5 rounded-md bg-zinc-50/90 px-2.5 py-2 text-xs text-zinc-600 shadow-sm dark:bg-zinc-950/90 dark:text-zinc-400">
        {isUniform ? (
          <span>
            All connections: <span className="font-medium text-zinc-800 dark:text-zinc-200">{baseLabel(links[0].type)}</span>
            <span className="text-zinc-400 dark:text-zinc-600"> · hover an edge for detail</span>
          </span>
        ) : (
          <span className="font-medium text-zinc-700 dark:text-zinc-300">Legend</span>
        )}
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-zinc-900 bg-zinc-300 dark:border-zinc-100" />
          Anchor (centered entity)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full border-2 border-dashed border-amber-400" />
          Existing customer
        </span>
        {domainsPresent.length > 0 && (
          <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            {domainsPresent.map((d) => (
              <span key={d} className="flex items-center gap-1">
                <span className={`inline-block h-2 w-2 rounded-full ${domainNodeFill(d)}`} />
                {d}
              </span>
            ))}
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${size.width} ${size.height}`}
        className="h-full w-full touch-none select-none rounded-lg border border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-950/50"
        onPointerMove={handleSvgPointerMove}
        onPointerDown={handleBackgroundPointerDown}
        onPointerUp={handleBackgroundPointerUp}
        onWheel={handleWheel}
      >
      <defs>
        <marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" className="fill-zinc-500 dark:fill-zinc-400" />
        </marker>
      </defs>
      <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
        <g>
          {links.map((link, i) => {
            const source = asNode(link.source);
            const target = asNode(link.target);
            if (!source || !target || source.x == null || target.x == null) return null;
            const midX = (source.x! + target.x!) / 2;
            const midY = (source.y! + target.y!) / 2;
            const end = edgeEndpoint(source, target);
            const touchesHovered = source.id === hoveredId || target.id === hoveredId;
            const inFocus = linkTouchesSelection(link);
            const showLabel = isUniform
              ? touchesHovered
              : !isDense || source.is_anchor || target.is_anchor || touchesHovered;
            return (
              <g key={i} opacity={inFocus ? 1 : 0.15}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={end.x}
                  y2={end.y}
                  className={touchesHovered ? "stroke-zinc-400 dark:stroke-zinc-500" : "stroke-zinc-300 dark:stroke-zinc-700"}
                  strokeWidth={touchesHovered ? 2 : 1.5}
                  markerEnd="url(#graph-arrow)"
                />
                {showLabel && (
                  <text
                    x={midX}
                    y={midY}
                    textAnchor="middle"
                    className="fill-zinc-500 text-[9px] stroke-zinc-50 dark:fill-zinc-400 dark:stroke-zinc-950"
                    style={{ paintOrder: "stroke", strokeWidth: 3 }}
                  >
                    {edgeLabel(link)}
                  </text>
                )}
              </g>
            );
          })}
        </g>
        <g>
          {nodes.map((node) => {
            if (node.x == null || node.y == null) return null;
            const r = nodeRadius(node);
            const isHovered = hoveredId === node.id;
            const isSelected = selectedId === node.id;
            const inFocus = nodeTouchesSelection(node.id);
            return (
              <g
                key={node.id}
                transform={`translate(${node.x},${node.y})`}
                className="cursor-pointer"
                opacity={inFocus ? 1 : 0.2}
                onPointerDown={(e) => handleNodePointerDown(e, node)}
                onPointerUp={(e) => handleNodePointerUp(e, node)}
                onPointerEnter={() => setHoveredId(node.id)}
                onPointerLeave={() => setHoveredId(null)}
              >
                {node.existing_customer && (
                  <circle r={r + 5} className="fill-none stroke-amber-400" strokeWidth={2.5} strokeDasharray="3 2" />
                )}
                <circle
                  r={r}
                  className={`${domainNodeFill(node.domain)} ${node.is_anchor ? "stroke-zinc-900 dark:stroke-zinc-100" : "stroke-white dark:stroke-zinc-950"} ${isSelected ? "stroke-blue-500 dark:stroke-blue-400" : ""}`}
                  strokeWidth={isSelected ? 3 : node.is_anchor ? 2.5 : 1.5}
                  opacity={isHovered ? 1 : 0.92}
                />
                <title>{node.name ?? "Unknown"}{node.existing_customer ? " — Existing Customer" : ""}</title>
                <text
                  y={r + 13}
                  textAnchor="middle"
                  className={`text-[10px] ${node.is_anchor ? "font-semibold fill-zinc-900 dark:fill-zinc-50" : "fill-zinc-600 dark:fill-zinc-400"}`}
                >
                  {truncate(node.name)}
                </text>
                {node.existing_customer && (
                  <text y={r + 25} textAnchor="middle" className="fill-amber-600 text-[9px] font-medium dark:fill-amber-400">
                    Existing Customer
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </g>
      </svg>
      </div>
      {selectedNode && (
        <GraphNodeDetail
          node={selectedNode}
          degree={degreeById.get(selectedNode.id) ?? 0}
          onClose={() => setSelectedId(null)}
          onRecenter={() => onRecenter(selectedNode.id)}
        />
      )}
    </div>
  );
}
