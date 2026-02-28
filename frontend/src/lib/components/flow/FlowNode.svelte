<!--
  FlowNode.svelte - Custom SvelteFlow node component.

  Supports four visual node types: entity, process-step, system, and document.
  Each type has a distinct icon, colour accent, and shape. Displays a primary
  label, optional subtitle, and a status indicator dot.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import { Circle, Cog, Monitor, FileText, Play, Flag } from 'lucide-svelte';
	import type { FlowNodeData, FlowNodeType } from './flow-types.js';

	// -----------------------------------------------------------------------
	// Props — matches the NodeProps shape that SvelteFlow passes to custom nodes.
	// We only destructure what we actually use.
	// -----------------------------------------------------------------------

	interface FlowNodeProps {
		id: string;
		data: FlowNodeData;
		selected?: boolean;
		dragging?: boolean;
		type?: string;
		[key: string]: unknown;
	}

	let { id, data, selected = false }: FlowNodeProps = $props();

	// -----------------------------------------------------------------------
	// Visual config per node type
	// -----------------------------------------------------------------------

	interface NodeStyle {
		borderColor: string;
		bgColor: string;
		accentColor: string;
		icon: typeof Circle;
		rounded: string;
	}

	const styleMap: Record<FlowNodeType, NodeStyle> = {
		entity: {
			borderColor: 'border-blue-400/60',
			bgColor: 'bg-blue-50 dark:bg-blue-950/40',
			accentColor: 'text-blue-500',
			icon: Circle,
			rounded: 'rounded-xl'
		},
		'process-step': {
			borderColor: 'border-teal-400/60',
			bgColor: 'bg-teal-50 dark:bg-teal-950/40',
			accentColor: 'text-teal-500',
			icon: Cog,
			rounded: 'rounded-lg'
		},
		system: {
			borderColor: 'border-violet-400/60',
			bgColor: 'bg-violet-50 dark:bg-violet-950/40',
			accentColor: 'text-violet-500',
			icon: Monitor,
			rounded: 'rounded-md'
		},
		document: {
			borderColor: 'border-amber-400/60',
			bgColor: 'bg-amber-50 dark:bg-amber-950/40',
			accentColor: 'text-amber-500',
			icon: FileText,
			rounded: 'rounded-lg'
		},
		'start-end': {
			borderColor: 'border-emerald-400/60',
			bgColor: 'bg-emerald-50 dark:bg-emerald-950/40',
			accentColor: 'text-emerald-600',
			icon: Play,
			rounded: 'rounded-full'
		}
	};

	// -----------------------------------------------------------------------
	// Status dot colours
	// -----------------------------------------------------------------------

	const statusColors: Record<NonNullable<FlowNodeData['status']>, string> = {
		active: 'bg-success',
		idle: 'bg-text-secondary',
		error: 'bg-danger',
		warning: 'bg-warning',
		completed: 'bg-blue-500'
	};

	// -----------------------------------------------------------------------
	// Derived values
	// -----------------------------------------------------------------------

	let nodeType = $derived(data.nodeType ?? 'entity');
	let style = $derived(styleMap[nodeType] ?? styleMap.entity);
	let statusColor = $derived(data.status ? (statusColors[data.status] ?? statusColors.idle) : null);
	let isActive = $derived(data.status === 'active');

	// For start-end nodes, differentiate icon: Start → Play, End → Flag
	let isEndNode = $derived(nodeType === 'start-end' && data.metadata?.sentinel === 'end');
	let endStyle = $derived<NodeStyle | null>(
		isEndNode
			? {
					borderColor: 'border-rose-400/60',
					bgColor: 'bg-rose-50 dark:bg-rose-950/40',
					accentColor: 'text-rose-600',
					icon: Flag,
					rounded: 'rounded-full'
				}
			: null
	);
	let effectiveStyle = $derived(endStyle ?? style);
	let IconComponent = $derived(effectiveStyle.icon);
</script>

<div
	class="flow-node relative border-2 px-4 py-2.5 shadow-sm transition-shadow
		{effectiveStyle.rounded} {effectiveStyle.borderColor} {effectiveStyle.bgColor}
		{selected ? 'ring-2 ring-accent shadow-md' : 'hover:shadow-md'}"
	data-node-id={id}
>
	<!-- Target handle (top) -->
	<Handle type="target" position={Position.Top} class="!border-border !bg-surface-elevated" />

	<div class="flex items-center gap-2.5">
		<!-- Icon -->
		<div class="flex-shrink-0 {effectiveStyle.accentColor}">
			<IconComponent size={16} />
		</div>

		<!-- Text content -->
		<div class="min-w-0 flex-1">
			<div class="flex items-center gap-1.5">
				<!-- Status dot -->
				{#if statusColor}
					<span
						class="inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full {statusColor}
							{isActive ? 'status-pulse' : ''}"
					></span>
				{/if}
				<span class="truncate text-xs font-semibold text-text-primary">
					{data.label}
				</span>
			</div>
			{#if data.subtitle}
				<span class="mt-0.5 block truncate text-[10px] text-text-secondary">
					{data.subtitle}
				</span>
			{/if}
		</div>
	</div>

	<!-- Source handle (bottom) -->
	<Handle type="source" position={Position.Bottom} class="!border-border !bg-surface-elevated" />
</div>

<style>
	@keyframes status-pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.4;
		}
	}

	.status-pulse {
		animation: status-pulse 2s ease-in-out infinite;
	}

	/* Ensure the node wrapper doesn't clip handles */
	.flow-node {
		min-width: 140px;
		max-width: 240px;
	}
</style>
