/**
 * Layout helpers and domain-model converters for SvelteFlow graphs.
 *
 * Provides a built-in topological/hierarchical (dagre-like) layout algorithm
 * and convenience functions to convert KG entities/relations and process
 * steps/dependencies into SvelteFlow Node/Edge arrays.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { Node, Edge } from '@xyflow/svelte';
import type {
	FlowNode,
	FlowNodeData,
	FlowEdge,
	FlowEdgeData,
	GraphEntity,
	GraphRelation,
	ProcessStep,
	ProcessDependency
} from './flow-types.js';

// ---------------------------------------------------------------------------
// Layout configuration
// ---------------------------------------------------------------------------

export interface DagreLayoutOptions {
	/** Horizontal spacing between nodes at the same level. @default 200 */
	nodeWidth?: number;
	/** Vertical spacing between levels. @default 120 */
	nodeHeight?: number;
	/** Horizontal gap between sibling nodes. @default 40 */
	horizontalGap?: number;
	/** Vertical gap between layers. @default 60 */
	verticalGap?: number;
	/** Layout direction. @default 'TB' (top-to-bottom) */
	direction?: 'TB' | 'LR';
}

// ---------------------------------------------------------------------------
// Dagre-like hierarchical layout (no external dependency)
// ---------------------------------------------------------------------------

/**
 * Auto-layout nodes in a top-to-bottom (or left-to-right) DAG arrangement.
 *
 * Uses Kahn's algorithm for topological ordering and then assigns x/y
 * positions layer-by-layer.  Nodes that form cycles or are disconnected
 * are placed at the end.
 */
export function layoutDagre<N extends Node = Node, E extends Edge = Edge>(
	nodes: N[],
	edges: E[],
	options: DagreLayoutOptions = {}
): N[] {
	const {
		nodeWidth = 200,
		nodeHeight = 60,
		horizontalGap = 40,
		verticalGap = 60,
		direction = 'TB'
	} = options;

	if (nodes.length === 0) return [];

	// Build adjacency and in-degree maps
	const inDegree = new Map<string, number>();
	const children = new Map<string, string[]>();
	const nodeIds = new Set(nodes.map((n) => n.id));

	for (const id of nodeIds) {
		inDegree.set(id, 0);
		children.set(id, []);
	}

	for (const edge of edges) {
		const src = typeof edge.source === 'string' ? edge.source : (edge.source as Node).id;
		const tgt = typeof edge.target === 'string' ? edge.target : (edge.target as Node).id;
		if (!nodeIds.has(src) || !nodeIds.has(tgt)) continue;
		children.get(src)!.push(tgt);
		inDegree.set(tgt, (inDegree.get(tgt) ?? 0) + 1);
	}

	// Kahn's topological sort -- produces layers
	const layers: string[][] = [];
	let frontier = [...nodeIds].filter((id) => inDegree.get(id) === 0);
	const placed = new Set<string>();

	while (frontier.length > 0) {
		layers.push(frontier);
		for (const id of frontier) placed.add(id);

		const next: string[] = [];
		for (const id of frontier) {
			for (const child of children.get(id) ?? []) {
				const deg = (inDegree.get(child) ?? 1) - 1;
				inDegree.set(child, deg);
				if (deg === 0 && !placed.has(child)) {
					next.push(child);
				}
			}
		}
		frontier = next;
	}

	// Catch any remaining nodes not placed (cycles / disconnected)
	const remaining = [...nodeIds].filter((id) => !placed.has(id));
	if (remaining.length > 0) {
		layers.push(remaining);
	}

	// Assign positions layer-by-layer
	const positionMap = new Map<string, { x: number; y: number }>();

	for (let layerIdx = 0; layerIdx < layers.length; layerIdx++) {
		const layer = layers[layerIdx];
		const layerWidth = layer.length * (nodeWidth + horizontalGap) - horizontalGap;
		const startOffset = -layerWidth / 2;

		for (let nodeIdx = 0; nodeIdx < layer.length; nodeIdx++) {
			const x = startOffset + nodeIdx * (nodeWidth + horizontalGap);
			const y = layerIdx * (nodeHeight + verticalGap);

			if (direction === 'TB') {
				positionMap.set(layer[nodeIdx], { x, y });
			} else {
				// LR: swap x/y
				positionMap.set(layer[nodeIdx], { x: y, y: x });
			}
		}
	}

	// Apply positions to nodes
	return nodes.map((node) => {
		const pos = positionMap.get(node.id);
		return pos ? { ...node, position: pos } : node;
	});
}

// ---------------------------------------------------------------------------
// Knowledge-graph converters
// ---------------------------------------------------------------------------

/** Map a KG entity type string to a FlowNodeType. */
function entityTypeToNodeType(type: string): FlowNodeData['nodeType'] {
	const lower = type.toLowerCase();
	if (lower === 'document' || lower === 'file') return 'document';
	if (lower === 'system' || lower === 'service' || lower === 'technology') return 'system';
	return 'entity';
}

/** Entity type colour mapping (mirrors KnowledgeGraphExplorer). */
const typeColors: Record<string, string> = {
	person: '#3b82f6',
	organization: '#8b5cf6',
	location: '#10b981',
	concept: '#f59e0b',
	technology: '#06b6d4',
	event: '#ef4444',
	document: '#6366f1',
	product: '#ec4899',
	process: '#14b8a6'
};

function entityColor(type: string): string {
	return typeColors[type.toLowerCase()] ?? '#6b7280';
}

/**
 * Convert an array of KG entities to SvelteFlow nodes.
 * Positions default to (0, 0) -- use {@link layoutDagre} afterwards.
 */
export function toFlowNodes(entities: GraphEntity[]): FlowNode[] {
	return entities.map((entity) => ({
		id: entity.id,
		type: entityTypeToNodeType(entity.type),
		position: { x: 0, y: 0 },
		data: {
			label: entity.name,
			subtitle: entity.type,
			nodeType: entityTypeToNodeType(entity.type),
			status: 'idle' as const,
			metadata: {
				...entity.properties,
				entityType: entity.type,
				color: entityColor(entity.type),
				source_documents: entity.source_documents
			}
		}
	}));
}

/**
 * Convert an array of KG relations to SvelteFlow edges.
 */
export function toFlowEdges(relations: GraphRelation[]): FlowEdge[] {
	return relations.map((rel) => ({
		id: rel.id,
		source: rel.source_id,
		target: rel.target_id,
		type: 'default',
		data: {
			label: rel.label,
			relation: 'association' as const,
			animated: false
		}
	}));
}

// ---------------------------------------------------------------------------
// Process discovery converters
// ---------------------------------------------------------------------------

/** Map a process step_type to a visual FlowNodeType. */
function stepTypeToNodeType(stepType: string | undefined): FlowNodeData['nodeType'] {
	if (!stepType) return 'process-step';
	const lower = stepType.toLowerCase();
	if (lower === 'system' || lower === 'integration') return 'system';
	if (lower === 'document' || lower === 'form') return 'document';
	return 'process-step';
}

/**
 * Convert process steps to SvelteFlow nodes.
 * Positions default to (0, 0) -- use {@link layoutDagre} afterwards.
 */
export function toProcessFlowNodes(steps: ProcessStep[]): FlowNode[] {
	return steps.map((step) => ({
		id: step.id,
		type: stepTypeToNodeType(step.step_type),
		position: { x: 0, y: 0 },
		data: {
			label: step.name,
			subtitle: step.description || step.step_type || undefined,
			nodeType: stepTypeToNodeType(step.step_type),
			status: 'idle' as const,
			metadata: {
				order: step.order,
				system_id: step.system_id,
				endpoint_id: step.endpoint_id,
				inputs: step.inputs,
				outputs: step.outputs
			}
		}
	}));
}

/**
 * Convert process dependencies to SvelteFlow edges.
 */
export function toProcessFlowEdges(dependencies: ProcessDependency[]): FlowEdge[] {
	return dependencies.map((dep, idx) => ({
		id: `dep-${idx}-${dep.source_step_id}-${dep.target_step_id}`,
		source: dep.source_step_id,
		target: dep.target_step_id,
		type: 'default',
		data: {
			label: dep.condition ?? undefined,
			relation: dep.condition ? ('condition' as const) : ('sequence' as const),
			animated: false
		}
	}));
}
