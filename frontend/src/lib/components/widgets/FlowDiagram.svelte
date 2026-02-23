<!--
  FlowDiagram.svelte - Chat widget for inline and panel flow diagrams.

  Accepts simplified node/edge props, converts them to FlowNode/FlowEdge
  format, auto-layouts via dagre when no positions are provided, and renders
  via FlowCanvas in read-only mode by default.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import FlowCanvas from '$lib/components/flow/FlowCanvas.svelte';
	import { layoutDagre } from '$lib/components/flow/flow-utils.js';
	import type {
		FlowNode as FlowNodeType,
		FlowEdge as FlowEdgeType,
		FlowNodeType as NodeTypeEnum
	} from '$lib/components/flow/flow-types.js';

	// -------------------------------------------------------------------
	// Simplified input types (from widget directive JSON)
	// -------------------------------------------------------------------

	interface SimplifiedNode {
		id: string;
		label: string;
		type?: string;
		x?: number;
		y?: number;
	}

	interface SimplifiedEdge {
		source: string;
		target: string;
		label?: string;
	}

	interface FlowDiagramProps {
		nodes: SimplifiedNode[];
		edges: SimplifiedEdge[];
		title?: string;
		interactive?: boolean;
		height?: string;
	}

	let {
		nodes,
		edges,
		title,
		interactive = false,
		height = '300px'
	}: FlowDiagramProps = $props();

	// -------------------------------------------------------------------
	// Valid node types recognised by FlowNode.svelte
	// -------------------------------------------------------------------

	const validNodeTypes = new Set<string>(['entity', 'process-step', 'system', 'document']);

	function resolveNodeType(type: string | undefined): NodeTypeEnum {
		if (type && validNodeTypes.has(type)) {
			return type as NodeTypeEnum;
		}
		return 'entity';
	}

	// -------------------------------------------------------------------
	// Convert simplified props to FlowNode / FlowEdge format
	// -------------------------------------------------------------------

	let flowNodes = $derived.by<FlowNodeType[]>(() => {
		const hasPositions = nodes.some((n) => n.x !== undefined && n.y !== undefined);

		const converted: FlowNodeType[] = nodes.map((n) => {
			const nodeType = resolveNodeType(n.type);
			return {
				id: n.id,
				type: nodeType,
				position: { x: n.x ?? 0, y: n.y ?? 0 },
				data: {
					label: n.label,
					nodeType
				}
			};
		});

		if (hasPositions) {
			return converted;
		}

		return layoutDagre(converted, flowEdges);
	});

	let flowEdges = $derived<FlowEdgeType[]>(
		edges.map((e, idx) => ({
			id: `e-${idx}-${e.source}-${e.target}`,
			source: e.source,
			target: e.target,
			type: 'default',
			data: {
				label: e.label,
				relation: 'default' as const,
				animated: false
			}
		}))
	);
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="flow-diagram-canvas" style:height>
		{#if flowNodes.length > 0}
			<FlowCanvas
				nodes={flowNodes}
				edges={flowEdges}
				{interactive}
				fitView={true}
				options={{
					controls: interactive,
					minimap: false,
					background: 'dots'
				}}
			/>
		{:else}
			<div class="flex h-full items-center justify-center">
				<span class="text-xs text-text-secondary">No nodes to display</span>
			</div>
		{/if}
	</div>
</div>

<style>
	.flow-diagram-canvas {
		min-height: 200px;
	}
</style>
