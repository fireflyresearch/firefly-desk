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

	let containerEl: HTMLDivElement = $state() as HTMLDivElement;
	let tooltipEl: HTMLDivElement = $state() as HTMLDivElement;

	// Plain variable (not $state) — same pattern as 2D viewport to avoid
	// $effect re-firing when the graph instance is first assigned.
	let graph: any = null;

	let status = $state<'loading' | 'ready' | 'empty' | 'error'>('loading');
	let errorMsg = $state('');
	let hoveredNode = $state<{
		name: string;
		type: string;
		x: number;
		y: number;
		confidence?: number;
		tags: string[];
		connections: number;
		sourceSystem?: string | null;
	} | null>(null);

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

				// Build a lookup for connection counts per node
				const connectionCounts = new Map<string, number>();
				for (const link of data.links) {
					connectionCounts.set(link.source, (connectionCounts.get(link.source) ?? 0) + 1);
					connectionCounts.set(link.target, (connectionCounts.get(link.target) ?? 0) + 1);
				}

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
					// Edge rendering — visible on dark background
					.linkColor((link: any) => {
						const srcColor = typeof link.source === 'object' ? link.source.color : null;
						return srcColor ? srcColor + '99' : 'rgba(148, 163, 184, 0.6)';
					})
					.linkWidth(0.8)
					.linkDirectionalArrowLength(3.5)
					.linkDirectionalArrowRelPos(1)
					.linkDirectionalArrowColor(() => 'rgba(148, 163, 184, 0.7)')
					.linkDirectionalParticles(1)
					.linkDirectionalParticleWidth(1.5)
					.linkDirectionalParticleColor((link: any) => {
						const srcColor = typeof link.source === 'object' ? link.source.color : null;
						return srcColor ? srcColor + 'aa' : 'rgba(148, 163, 184, 0.5)';
					})
					// Interactions
					.onNodeClick((node: any) => {
						if (node?.entity) onNodeSelect(node.entity);
					})
					.onNodeHover((node: any) => {
						containerEl.style.cursor = node ? 'pointer' : 'default';
						if (node) {
							const coords = instance.graph2ScreenCoords(node.x, node.y, node.z);
							const entity = node.entity as GraphEntity;
							const tags: string[] = [];
							if (entity.properties?.tags) {
								const rawTags = entity.properties.tags;
								if (Array.isArray(rawTags)) tags.push(...rawTags.map(String));
							}
							if (entity.properties?.category) {
								tags.push(String(entity.properties.category));
							}
							hoveredNode = {
								name: node.name,
								type: node.type,
								x: coords.x,
								y: coords.y,
								confidence: entity.confidence,
								tags,
								connections: connectionCounts.get(node.id) ?? 0,
								sourceSystem: entity.source_system
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
			class="pointer-events-none absolute z-50 max-w-xs rounded-lg border border-white/10 bg-slate-900/95 px-3 py-2.5 text-xs shadow-xl backdrop-blur-md"
			style="left: {hoveredNode.x + 14}px; top: {hoveredNode.y - 14}px;"
		>
			<div class="flex items-center gap-2">
				<span
					class="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
					style="background-color: {getColor(hoveredNode.type)};"
				></span>
				<span class="font-semibold text-white">{hoveredNode.name}</span>
			</div>
			<div class="mt-1 flex items-center gap-2 text-[10px] text-slate-400">
				<span class="rounded bg-white/10 px-1.5 py-0.5 capitalize">{hoveredNode.type}</span>
				{#if hoveredNode.confidence != null}
					<span>{Math.round(hoveredNode.confidence * 100)}% confidence</span>
				{/if}
				{#if hoveredNode.connections > 0}
					<span>{hoveredNode.connections} connection{hoveredNode.connections === 1 ? '' : 's'}</span>
				{/if}
			</div>
			{#if hoveredNode.tags.length > 0}
				<div class="mt-1.5 flex flex-wrap gap-1">
					{#each hoveredNode.tags.slice(0, 5) as tag}
						<span class="rounded-full bg-accent/20 px-1.5 py-0.5 text-[10px] text-accent">{tag}</span>
					{/each}
					{#if hoveredNode.tags.length > 5}
						<span class="text-[10px] text-slate-500">+{hoveredNode.tags.length - 5}</span>
					{/if}
				</div>
			{/if}
			{#if hoveredNode.sourceSystem}
				<div class="mt-1 text-[10px] text-slate-500">from {hoveredNode.sourceSystem}</div>
			{/if}
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
				{filteredEntities.length} nodes · {filteredRelations.length} edges
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
