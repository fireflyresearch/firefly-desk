<!--
  FlowCanvas.svelte - Base SvelteFlow wrapper component.

  Theme-aware, responsive canvas that renders nodes and edges using the
  @xyflow/svelte library. Supports custom node/edge types (FlowNode,
  FlowEdge), configurable zoom/pan/minimap/controls, and event callbacks
  for node click, edge click, and pane click. Designed for reuse across
  the KG explorer, process canvas, and chat widget flow diagrams.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		SvelteFlow,
		Background,
		Controls,
		MiniMap,
		BackgroundVariant,
		type NodeTypes,
		type EdgeTypes
	} from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';

	import FlowNode from './FlowNode.svelte';
	import FlowEdge from './FlowEdge.svelte';
	import type {
		FlowNode as FlowNodeType,
		FlowEdge as FlowEdgeType,
		FlowCanvasOptions
	} from './flow-types.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface FlowCanvasProps {
		/** Array of flow nodes to render. */
		nodes: FlowNodeType[];
		/** Array of flow edges to render. */
		edges: FlowEdgeType[];
		/** Fit the viewport to show all nodes on mount. @default true */
		fitView?: boolean;
		/** Allow user interaction (dragging, selecting). @default true */
		interactive?: boolean;
		/** Canvas behavioural options (minimap, controls, background, zoom). */
		options?: FlowCanvasOptions;
		/** Called when a user clicks a node. */
		onNodeClick?: (node: FlowNodeType) => void;
		/** Called when a user clicks an edge. */
		onEdgeClick?: (edge: FlowEdgeType) => void;
		/** Called when a user clicks the empty pane. */
		onPaneClick?: () => void;
		/** Optional CSS class for the outer container. */
		class?: string;
	}

	let {
		nodes,
		edges,
		fitView = true,
		interactive = true,
		options = {},
		onNodeClick,
		onEdgeClick,
		onPaneClick,
		class: className = ''
	}: FlowCanvasProps = $props();

	// -----------------------------------------------------------------------
	// Custom type registrations
	// -----------------------------------------------------------------------

	const nodeTypes: NodeTypes = {
		entity: FlowNode as unknown as NodeTypes[string],
		'process-step': FlowNode as unknown as NodeTypes[string],
		system: FlowNode as unknown as NodeTypes[string],
		document: FlowNode as unknown as NodeTypes[string]
	};

	const edgeTypes: EdgeTypes = {
		default: FlowEdge as unknown as EdgeTypes[string]
	};

	// -----------------------------------------------------------------------
	// Options with defaults
	// -----------------------------------------------------------------------

	let showMinimap = $derived(options.minimap ?? false);
	let showControls = $derived(options.controls ?? true);
	let bgVariant = $derived(options.background ?? 'dots');
	let minZoom = $derived(options.minZoom ?? 0.25);
	let maxZoom = $derived(options.maxZoom ?? 4);
	let panOnDrag = $derived(options.panOnDrag ?? true);
	let zoomOnScroll = $derived(options.zoomOnScroll ?? true);

	// Map string variant to BackgroundVariant enum
	const bgVariantMap: Record<string, BackgroundVariant> = {
		dots: BackgroundVariant.Dots,
		lines: BackgroundVariant.Lines,
		cross: BackgroundVariant.Cross
	};

	let backgroundVariant = $derived(bgVariantMap[bgVariant] ?? BackgroundVariant.Dots);
	let showBackground = $derived(bgVariant !== 'none');

	// -----------------------------------------------------------------------
	// Event handlers -- adapt from SvelteFlow's event shape to our simpler
	// callback signatures
	// -----------------------------------------------------------------------

	function handleNodeClick({ node }: { node: FlowNodeType; event: MouseEvent | TouchEvent }) {
		onNodeClick?.(node);
	}

	function handleEdgeClick({ edge }: { edge: FlowEdgeType; event: MouseEvent }) {
		onEdgeClick?.(edge);
	}

	function handlePaneClick() {
		onPaneClick?.();
	}
</script>

<div class="flow-canvas-container h-full w-full {className}">
	<SvelteFlow
		{nodes}
		{edges}
		{nodeTypes}
		{edgeTypes}
		{fitView}
		{minZoom}
		{maxZoom}
		{panOnDrag}
		{zoomOnScroll}
		nodesDraggable={interactive}
		nodesConnectable={false}
		elementsSelectable={interactive}
		onnodeclick={handleNodeClick}
		onedgeclick={handleEdgeClick}
		onpaneclick={handlePaneClick}
		colorMode="system"
		proOptions={{ hideAttribution: true }}
	>
		{#if showBackground}
			<Background
				variant={backgroundVariant}
				gap={20}
				patternColor="var(--color-border)"
			/>
		{/if}

		{#if showControls}
			<Controls
				showLock={false}
			/>
		{/if}

		{#if showMinimap}
			<MiniMap
				nodeColor="var(--color-accent)"
				maskColor="var(--color-surface-secondary)"
			/>
		{/if}
	</SvelteFlow>
</div>

<style>
	.flow-canvas-container {
		position: relative;
	}

	/*
	 * Theme overrides: map the project's CSS custom properties into
	 * @xyflow/svelte's internal CSS variables so the canvas automatically
	 * follows light / dark mode.
	 */
	.flow-canvas-container :global(.svelte-flow) {
		--xy-background-color: var(--color-surface);
		--xy-node-color: var(--color-text-primary);
		--xy-node-border: var(--color-border);
		--xy-node-background-color: var(--color-surface-elevated);
		--xy-edge-stroke: var(--color-border);
		--xy-connectionline-stroke: var(--color-accent);
		--xy-minimap-background-color: var(--color-surface-secondary);
		--xy-controls-button-background-color: var(--color-surface-elevated);
		--xy-controls-button-border-color: var(--color-border);
		--xy-controls-button-color: var(--color-text-secondary);
	}

	.flow-canvas-container :global(.svelte-flow__controls button:hover) {
		background-color: var(--color-surface-hover);
		color: var(--color-text-primary);
	}
</style>
