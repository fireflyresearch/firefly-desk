<!--
  KGGraphViewport3D.svelte - 3D force-directed knowledge graph renderer.

  Renders entities as colored spheres in a WebGL 3D space using 3d-force-graph.
  Supports click-to-select, hover-highlight, zoom/orbit, and fit-to-view.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { Loader2, Network, Maximize2 } from 'lucide-svelte';
	import type { GraphEntity, GraphRelation } from '$lib/components/flow/flow-types.js';

	interface Props {
		entities: GraphEntity[];
		relations: GraphRelation[];
		hiddenTypes: Set<string>;
		selectedId: string | null;
		typeColors: Record<string, string>;
		onNodeSelect: (entity: GraphEntity) => void;
		onShowAllTypes: () => void;
	}

	let {
		entities,
		relations,
		hiddenTypes,
		selectedId,
		typeColors,
		onNodeSelect,
		onShowAllTypes
	}: Props = $props();

	let containerEl: HTMLDivElement;
	let tooltipEl: HTMLDivElement;

	// Plain variable (not $state) — same pattern as 2D viewport to avoid
	// $effect re-firing when the graph instance is first assigned.
	let graph: any = null;

	let status = $state<'loading' | 'ready' | 'empty' | 'error'>('loading');
	let errorMsg = $state('');
	let hoveredNode = $state<{ name: string; type: string; x: number; y: number } | null>(null);

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function getColor(type: string): string {
		return typeColors[type.toLowerCase()] ?? typeColors.default ?? '#6b7280';
	}

	// -----------------------------------------------------------------------
	// Derived filtered data
	// -----------------------------------------------------------------------

	let filteredEntities = $derived.by(() => {
		if (hiddenTypes.size === 0) return entities;
		return entities.filter((e) => !hiddenTypes.has((e.type ?? '').toLowerCase()));
	});

	let filteredIds = $derived(new Set(filteredEntities.map((e) => e.id)));

	let filteredRelations = $derived.by(() => {
		return relations.filter(
			(r) => filteredIds.has(r.source_id) && filteredIds.has(r.target_id)
		);
	});

	// -----------------------------------------------------------------------
	// Graph data conversion
	// -----------------------------------------------------------------------

	interface GraphNode {
		id: string;
		name: string;
		type: string;
		val: number;
		color: string;
		entity: GraphEntity;
		x?: number;
		y?: number;
		z?: number;
	}

	interface GraphLink {
		source: string;
		target: string;
		label: string;
	}

	function buildGraphData(): { nodes: GraphNode[]; links: GraphLink[] } {
		const linkCounts = new Map<string, number>();
		for (const r of filteredRelations) {
			linkCounts.set(r.source_id, (linkCounts.get(r.source_id) ?? 0) + 1);
			linkCounts.set(r.target_id, (linkCounts.get(r.target_id) ?? 0) + 1);
		}

		const nodes: GraphNode[] = filteredEntities.map((e) => ({
			id: e.id,
			name: e.name ?? 'Unnamed',
			type: (e.type ?? 'unknown').toLowerCase(),
			val: Math.max(2, Math.sqrt(linkCounts.get(e.id) ?? 1) * 2),
			color: getColor(e.type ?? 'unknown'),
			entity: e
		}));

		const links: GraphLink[] = filteredRelations.map((r) => ({
			source: r.source_id,
			target: r.target_id,
			label: r.label || r.relation_type.replace(/_/g, ' ')
		}));

		return { nodes, links };
	}

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	function fitToView() {
		if (graph) graph.zoomToFit(400, 40);
	}

	onMount(() => {
		const raf = requestAnimationFrame(async () => {
			const rect = containerEl.getBoundingClientRect();

			if (rect.width === 0 || rect.height === 0) {
				errorMsg = `Container has zero dimensions (${Math.round(rect.width)}x${Math.round(rect.height)}). Check parent layout.`;
				status = 'error';
				return;
			}

			containerEl.style.width = `${rect.width}px`;
			containerEl.style.height = `${rect.height}px`;

			const data = buildGraphData();
			if (data.nodes.length === 0) {
				status = 'empty';
				return;
			}

			try {
				// The TS types declare `new ForceGraph3D(el)` but the runtime API
				// is a factory: `ForceGraph3D()(el)`. Cast to satisfy the compiler.
				const mod = await import('3d-force-graph');
				const ForceGraph3D = mod.default as unknown as (
					configOptions?: Record<string, unknown>
				) => (element: HTMLElement) => any;

				const instance = ForceGraph3D()(containerEl)
					.width(rect.width)
					.height(rect.height)
					.backgroundColor('#0f172a')
					.graphData(data)
					// Node rendering
					.nodeVal('val')
					.nodeColor('color')
					.nodeLabel('')
					.nodeOpacity(0.92)
					.nodeResolution(12)
					// Edge rendering
					.linkColor(() => 'rgba(100, 116, 139, 0.35)')
					.linkWidth(0.5)
					.linkDirectionalArrowLength(3)
					.linkDirectionalArrowRelPos(1)
					.linkDirectionalArrowColor(() => 'rgba(100, 116, 139, 0.5)')
					.linkDirectionalParticles(1)
					.linkDirectionalParticleWidth(1.2)
					.linkDirectionalParticleColor(() => 'rgba(100, 116, 139, 0.3)')
					// Interactions
					.onNodeClick((node: any) => {
						if (node?.entity) onNodeSelect(node.entity);
					})
					.onNodeHover((node: any) => {
						containerEl.style.cursor = node ? 'pointer' : 'default';
						if (node) {
							const coords = instance.graph2ScreenCoords(node.x, node.y, node.z);
							hoveredNode = {
								name: node.name,
								type: node.type,
								x: coords.x,
								y: coords.y
							};
						} else {
							hoveredNode = null;
						}
					})
					.onBackgroundClick(() => {
						hoveredNode = null;
					});

				// Let the simulation settle briefly, then fit the view
				setTimeout(() => instance.zoomToFit(400, 40), 500);

				graph = instance;
				status = 'ready';
			} catch (err) {
				console.error('[KGGraphViewport3D] Init failed:', err);
				errorMsg = err instanceof Error ? err.message : String(err);
				status = 'error';
			}
		});

		// ResizeObserver
		const ro = new ResizeObserver(() => {
			const r = containerEl.getBoundingClientRect();
			containerEl.style.width = `${r.width}px`;
			containerEl.style.height = `${r.height}px`;
			if (graph) {
				graph.width(r.width).height(r.height);
			}
		});
		ro.observe(containerEl);

		return () => {
			cancelAnimationFrame(raf);
			ro.disconnect();
			if (graph) {
				graph._destructor();
				graph = null;
			}
		};
	});

	// -----------------------------------------------------------------------
	// Reactive updates
	// -----------------------------------------------------------------------

	$effect(() => {
		void filteredEntities;
		void filteredRelations;

		if (graph && filteredEntities.length > 0) {
			graph.graphData(buildGraphData());
		} else if (graph && filteredEntities.length === 0) {
			status = 'empty';
		}
	});
</script>

<div class="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-[#0f172a]">
	<div bind:this={containerEl} class="absolute inset-0"></div>

	<!-- Tooltip -->
	{#if hoveredNode}
		<div
			bind:this={tooltipEl}
			class="pointer-events-none absolute z-50 rounded-md border border-border bg-surface/95 px-2 py-1.5 text-xs shadow-lg backdrop-blur-sm"
			style="left: {hoveredNode.x + 12}px; top: {hoveredNode.y - 10}px;"
		>
			<div class="font-medium text-text-primary">{hoveredNode.name}</div>
			<div class="text-text-secondary">{hoveredNode.type}</div>
		</div>
	{/if}

	{#if status === 'loading'}
		<div class="pointer-events-none absolute inset-0 flex items-center justify-center">
			<div class="flex flex-col items-center gap-2 text-center">
				<Loader2 size={20} class="animate-spin text-blue-400/60" />
				<span class="text-xs text-blue-300/50">Rendering 3D graph...</span>
			</div>
		</div>
	{:else if status === 'empty'}
		<div class="absolute inset-0 flex flex-col items-center justify-center text-text-secondary">
			<Network size={48} strokeWidth={1} class="mb-2 opacity-30" />
			<p class="text-sm">No entities match the current filters.</p>
			{#if hiddenTypes.size > 0}
				<button
					type="button"
					onclick={onShowAllTypes}
					class="mt-2 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90"
				>
					Show All Types
				</button>
			{/if}
		</div>
	{:else if status === 'error'}
		<div class="absolute inset-0 flex flex-col items-center justify-center text-text-secondary">
			<p class="text-sm text-danger">3D graph render failed: {errorMsg}</p>
		</div>
	{/if}

	<!-- Controls overlay -->
	<div class="absolute bottom-3 right-3 flex items-center gap-1.5">
		{#if status === 'ready'}
			<span class="rounded bg-surface/80 px-1.5 py-0.5 text-[10px] text-text-secondary/50 backdrop-blur-sm">
				{filteredEntities.length} nodes
			</span>
		{/if}
		<button
			type="button"
			onclick={fitToView}
			class="rounded-md border border-border bg-surface/90 p-1.5 text-text-secondary shadow-sm backdrop-blur-sm transition-colors hover:bg-surface-hover"
			title="Fit to View"
		>
			<Maximize2 size={14} />
		</button>
	</div>
</div>
