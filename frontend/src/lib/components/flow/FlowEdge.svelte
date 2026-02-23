<!--
  FlowEdge.svelte - Custom SvelteFlow edge component.

  Renders a bezier edge path with optional label support, animation for
  active flows, and colour-coding by relation type.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { BaseEdge, EdgeLabel, getBezierPath, type Position } from '@xyflow/svelte';
	import type { FlowEdgeData, FlowEdgeRelation } from './flow-types.js';

	// -----------------------------------------------------------------------
	// Props — matches the EdgeProps shape that SvelteFlow passes to custom edges.
	// -----------------------------------------------------------------------

	interface FlowEdgeProps {
		id: string;
		sourceX: number;
		sourceY: number;
		targetX: number;
		targetY: number;
		sourcePosition: Position;
		targetPosition: Position;
		data?: FlowEdgeData;
		selected?: boolean;
		markerStart?: string;
		markerEnd?: string;
		style?: string;
		interactionWidth?: number;
		label?: string;
		labelStyle?: string;
		[key: string]: unknown;
	}

	let {
		id,
		sourceX,
		sourceY,
		targetX,
		targetY,
		sourcePosition,
		targetPosition,
		data,
		selected = false,
		markerStart,
		markerEnd,
		style,
		interactionWidth
	}: FlowEdgeProps = $props();

	// -----------------------------------------------------------------------
	// Relation colour mapping
	// -----------------------------------------------------------------------

	const relationColors: Record<FlowEdgeRelation, string> = {
		default: 'var(--color-border)',
		dependency: 'var(--color-accent)',
		'data-flow': 'var(--color-success)',
		association: 'var(--color-text-secondary)',
		condition: 'var(--color-warning)',
		sequence: 'var(--color-border)'
	};

	// -----------------------------------------------------------------------
	// Derived values
	// -----------------------------------------------------------------------

	let relation = $derived((data?.relation ?? 'default') as FlowEdgeRelation);
	let edgeColor = $derived(relationColors[relation] ?? relationColors.default);
	let isAnimated = $derived(data?.animated ?? false);
	let edgeLabel = $derived(data?.label ?? undefined);

	let edgeStyle = $derived(
		[
			`stroke: ${selected ? 'var(--color-accent)' : edgeColor}`,
			`stroke-width: ${selected ? 2.5 : 1.5}`,
			isAnimated ? 'stroke-dasharray: 5 5' : '',
			style ?? ''
		]
			.filter(Boolean)
			.join('; ')
	);

	let pathData = $derived(
		getBezierPath({
			sourceX,
			sourceY,
			targetX,
			targetY,
			sourcePosition,
			targetPosition
		})
	);
</script>

<g class={isAnimated ? 'flow-edge-animated' : ''}>
	<BaseEdge
		{id}
		path={pathData[0]}
		{markerStart}
		{markerEnd}
		{interactionWidth}
		style={edgeStyle}
	/>
	{#if edgeLabel}
		<EdgeLabel
			x={pathData[1]}
			y={pathData[2]}
		>
			<span
				class="rounded border border-border bg-surface-elevated px-1.5 py-0.5 text-[10px] font-medium text-text-secondary shadow-sm"
			>
				{edgeLabel}
			</span>
		</EdgeLabel>
	{/if}
</g>

<style>
	@keyframes flow-dash {
		to {
			stroke-dashoffset: -20;
		}
	}

	:global(.flow-edge-animated path) {
		animation: flow-dash 0.8s linear infinite;
	}
</style>
