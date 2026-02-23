/**
 * TypeScript types for SvelteFlow graph visualization components.
 *
 * Shared type definitions used across the KG explorer, process canvas,
 * and chat widget flow diagrams.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { Node, Edge } from '@xyflow/svelte';

// ---------------------------------------------------------------------------
// Node type discriminator
// ---------------------------------------------------------------------------

/** Supported custom node types rendered by FlowNode. */
export type FlowNodeType = 'entity' | 'process-step' | 'system' | 'document';

// ---------------------------------------------------------------------------
// Node data payloads
// ---------------------------------------------------------------------------

/** Data payload attached to every custom flow node. */
export interface FlowNodeData extends Record<string, unknown> {
	/** Primary display label. */
	label: string;
	/** Optional secondary line beneath the label. */
	subtitle?: string;
	/** Visual node type -- determines icon, color, and shape. */
	nodeType: FlowNodeType;
	/** Optional status indicator shown as a colored dot. */
	status?: 'active' | 'idle' | 'error' | 'warning' | 'completed';
	/** Arbitrary metadata for downstream consumers. */
	metadata?: Record<string, unknown>;
}

/** A SvelteFlow `Node` narrowed to our custom data shape. */
export type FlowNode = Node<FlowNodeData, FlowNodeType>;

// ---------------------------------------------------------------------------
// Edge data payloads
// ---------------------------------------------------------------------------

/** Relation categories that control edge colour. */
export type FlowEdgeRelation =
	| 'default'
	| 'dependency'
	| 'data-flow'
	| 'association'
	| 'condition'
	| 'sequence';

/** Data payload attached to every custom flow edge. */
export interface FlowEdgeData extends Record<string, unknown> {
	/** Optional label rendered on the edge path. */
	label?: string;
	/** Whether the edge should animate (e.g. active data flow). */
	animated?: boolean;
	/** Relation category -- drives colour coding. */
	relation?: FlowEdgeRelation;
}

/** A SvelteFlow `Edge` narrowed to our custom data shape. */
export type FlowEdge = Edge<FlowEdgeData>;

// ---------------------------------------------------------------------------
// Canvas options
// ---------------------------------------------------------------------------

/** Configuration bag for `FlowCanvas` behavioural options. */
export interface FlowCanvasOptions {
	/** Show the minimap plugin. @default false */
	minimap?: boolean;
	/** Show the controls plugin (zoom in/out, fit). @default true */
	controls?: boolean;
	/** Background pattern. @default 'dots' */
	background?: 'dots' | 'lines' | 'cross' | 'none';
	/** Min zoom level. @default 0.25 */
	minZoom?: number;
	/** Max zoom level. @default 4 */
	maxZoom?: number;
	/** Allow panning by dragging. @default true */
	panOnDrag?: boolean;
	/** Allow zooming via scroll. @default true */
	zoomOnScroll?: boolean;
}

// ---------------------------------------------------------------------------
// Domain model interfaces (mirroring backend Pydantic models)
// ---------------------------------------------------------------------------

/** Knowledge-graph entity as returned by the API. */
export interface GraphEntity {
	id: string;
	name: string;
	type: string;
	properties: Record<string, unknown>;
	source_documents?: string[];
}

/** Knowledge-graph relation as returned by the API. */
export interface GraphRelation {
	id: string;
	source_id: string;
	target_id: string;
	label: string;
}

/** A step within a discovered business process (mirrors backend ProcessStep). */
export interface ProcessStep {
	id: string;
	name: string;
	description?: string;
	step_type?: string;
	system_id?: string | null;
	endpoint_id?: string | null;
	order: number;
	inputs?: string[];
	outputs?: string[];
}

/** A dependency edge between two process steps (mirrors backend ProcessDependency). */
export interface ProcessDependency {
	source_step_id: string;
	target_step_id: string;
	condition?: string | null;
}
