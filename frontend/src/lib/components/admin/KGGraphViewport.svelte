<!--
  KGGraphViewport.svelte - Cytoscape.js knowledge graph renderer.

  Renders entities as typed/colored nodes with force-directed layout.
  Supports click-to-select, hover-highlight neighbors, zoom/pan, and fit-to-view.

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

	// IMPORTANT: cy is a plain variable, NOT $state. This prevents the $effect
	// from firing when cy is first assigned during onMount, which would wipe the
	// graph via cy.json() before the initial layout finishes rendering.
	let cy: any = null;
	let _layoutName = 'cose';

	let status = $state<'loading' | 'ready' | 'empty' | 'error'>('loading');
	let errorMsg = $state('');

	// -----------------------------------------------------------------------
	// Node shape mapping
	// -----------------------------------------------------------------------

	const typeShapes: Record<string, string> = {
		system: 'round-rectangle',
		service: 'ellipse',
		process: 'diamond',
		data_object: 'hexagon',
		concept: 'round-triangle',
		role: 'star',
		person: 'ellipse',
		document: 'round-rectangle',
		organization: 'rectangle',
		location: 'pentagon',
		technology: 'octagon',
		default: 'ellipse'
	};

	function getShape(type: string): string {
		return typeShapes[type.toLowerCase()] ?? typeShapes.default;
	}

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
	// Cytoscape element conversion
	// -----------------------------------------------------------------------

	function toCytoscapeElements() {
		const nodes = filteredEntities.map((e) => ({
			data: {
				id: e.id,
				label: e.name ?? 'Unnamed',
				type: (e.type ?? 'unknown').toLowerCase(),
				entity: e
			}
		}));

		const edges = filteredRelations.map((r) => ({
			data: {
				id: r.id,
				source: r.source_id,
				target: r.target_id,
				label: r.label || r.relation_type.replace(/_/g, ' '),
				relation: r
			}
		}));

		return [...nodes, ...edges];
	}

	// -----------------------------------------------------------------------
	// Stylesheet
	// -----------------------------------------------------------------------

	function buildStylesheet() {
		const baseStyles = [
			{
				selector: 'node',
				style: {
					label: 'data(label)',
					'text-valign': 'bottom',
					'text-halign': 'center',
					'text-margin-y': 6,
					'font-size': 10,
					'font-weight': 600,
					'font-family': 'system-ui, -apple-system, sans-serif',
					color: '#cbd5e1',
					'text-outline-color': '#0f172a',
					'text-outline-width': 2,
					'text-max-width': '100px',
					'text-wrap': 'ellipsis',
					width: 28,
					height: 28,
					'border-width': 2,
					'border-opacity': 0.3,
					'overlay-padding': 4
				}
			},
			{
				selector: 'edge',
				style: {
					width: 1.5,
					'line-color': '#334155',
					'target-arrow-color': '#475569',
					'target-arrow-shape': 'triangle',
					'curve-style': 'bezier',
					'arrow-scale': 0.8,
					label: 'data(label)',
					'font-size': 8,
					color: '#64748b',
					'text-rotation': 'autorotate',
					'text-background-color': '#0f172a',
					'text-background-opacity': 0.85,
					'text-background-padding': '2px',
					'text-background-shape': 'roundrectangle'
				}
			},
			{
				selector: 'node:selected',
				style: {
					'border-width': 3,
					'border-color': '#818cf8',
					'border-opacity': 1,
					'overlay-color': '#818cf8',
					'overlay-opacity': 0.08
				}
			},
			{
				selector: '.highlighted',
				style: { 'border-width': 2, 'border-opacity': 0.8, 'font-weight': 700, 'z-index': 10 }
			},
			{
				selector: '.dimmed',
				style: { opacity: 0.2 }
			},
			{
				selector: 'edge.highlighted',
				style: { width: 2.5, 'line-color': '#475569', 'target-arrow-color': '#64748b', 'z-index': 10, opacity: 1 }
			},
			{
				selector: 'edge.dimmed',
				style: { opacity: 0.08 }
			}
		];

		const allTypes = new Set(entities.map((e) => (e.type ?? 'unknown').toLowerCase()));
		const typeStyles = [...allTypes].map((type) => ({
			selector: `node[type = "${type}"]`,
			style: {
				'background-color': getColor(type),
				'border-color': getColor(type),
				shape: getShape(type)
			}
		}));

		return [...baseStyles, ...typeStyles];
	}

	// -----------------------------------------------------------------------
	// Graph lifecycle — single initialization path via onMount
	// -----------------------------------------------------------------------

	function destroyGraph() {
		if (cy) {
			cy.destroy();
			cy = null;
		}
	}

	function fitToView() {
		if (cy) cy.fit(undefined, 40);
	}

	onMount(() => {
		// Use requestAnimationFrame to ensure the container has painted dimensions
		const raf = requestAnimationFrame(async () => {
			const rect = containerEl.getBoundingClientRect();

			if (rect.width === 0 || rect.height === 0) {
				errorMsg = `Container has zero dimensions (${Math.round(rect.width)}x${Math.round(rect.height)}). Check parent layout.`;
				status = 'error';
				return;
			}

			// Set explicit pixel dimensions on the container. Cytoscape reads
			// clientWidth/clientHeight internally, which can return 0 for
			// absolutely-positioned elements in certain flex layouts even though
			// getBoundingClientRect() returns correct values.
			containerEl.style.width = `${rect.width}px`;
			containerEl.style.height = `${rect.height}px`;

			const elements = toCytoscapeElements();
			if (elements.length === 0) {
				status = 'empty';
				return;
			}

			try {
				// Import cytoscape
				const cytoscapeMod = await import('cytoscape');
				const cytoscape = cytoscapeMod.default;

				// Import and register fcose
				let layoutName = 'cose'; // fallback to built-in
				try {
					const fcoseMod = await import('cytoscape-fcose');
					const fcose = fcoseMod.default ?? fcoseMod;
					if (typeof fcose === 'function') {
						cytoscape.use(fcose);
						layoutName = 'fcose';
					}
				} catch (fcoseErr) {
					console.warn('[KGGraphViewport] fcose unavailable, using cose:', fcoseErr);
				}
				_layoutName = layoutName;

				// Create cytoscape with synchronous layout (animate: false).
				// This avoids ALL timing/event-ordering issues.
				const instance = cytoscape({
					container: containerEl,
					elements,
					style: buildStylesheet() as any,
					layout: {
						name: layoutName,
						animate: false,
						randomize: true,
						quality: 'default',
						nodeSeparation: 80,
						idealEdgeLength: 120,
						nodeRepulsion: layoutName === 'fcose' ? 6000 : 4500,
						gravity: 0.25,
						gravityRange: 3.8
					} as any,
					minZoom: 0.15,
					maxZoom: 5,
					wheelSensitivity: 0.3,
					boxSelectionEnabled: false,
					selectionType: 'single'
				});

				// Layout is done synchronously — fit immediately
				instance.resize();
				instance.fit(undefined, 40);

				// Event handlers
				instance.on('tap', 'node', (evt: any) => {
					const entity = evt.target.data('entity');
					if (entity) onNodeSelect(entity);
				});

				instance.on('tap', (evt: any) => {
					if (evt.target === instance) {
						instance.elements().removeClass('highlighted dimmed');
					}
				});

				instance.on('mouseover', 'node', (evt: any) => {
					const node = evt.target;
					const neighborhood = node.closedNeighborhood();
					instance.elements().addClass('dimmed');
					neighborhood.removeClass('dimmed').addClass('highlighted');
					containerEl.style.cursor = 'pointer';
				});

				instance.on('mouseout', 'node', () => {
					instance.elements().removeClass('highlighted dimmed');
					containerEl.style.cursor = 'default';
				});

				cy = instance;
				status = 'ready';

			} catch (err) {
				console.error('[KGGraphViewport] Init failed:', err);
				errorMsg = err instanceof Error ? err.message : String(err);
				status = 'error';
			}
		});

		// ResizeObserver — update explicit dimensions and tell cytoscape to resize
		const ro = new ResizeObserver(() => {
			const r = containerEl.getBoundingClientRect();
			containerEl.style.width = `${r.width}px`;
			containerEl.style.height = `${r.height}px`;
			if (cy) {
				cy.resize();
				cy.fit(undefined, 40);
			}
		});
		ro.observe(containerEl);

		return () => {
			cancelAnimationFrame(raf);
			ro.disconnect();
			destroyGraph();
		};
	});

	// -----------------------------------------------------------------------
	// Reactive updates — only fires when filters change, NOT on init.
	// cy is a plain variable so it is NOT tracked as a dependency.
	// -----------------------------------------------------------------------

	$effect(() => {
		// Track filter changes
		void filteredEntities;
		void filteredRelations;

		if (cy && filteredEntities.length > 0) {
			cy.json({ elements: toCytoscapeElements() });
			cy.style(buildStylesheet());
			const layout = cy.layout({
				name: _layoutName,
				animate: true,
				animationDuration: 600,
				randomize: false,
				quality: 'default',
				nodeSeparation: 80,
				idealEdgeLength: 120,
				nodeRepulsion: _layoutName === 'fcose' ? 6000 : 4500,
				gravity: 0.25
			} as any);
			layout.run();
		} else if (cy && filteredEntities.length === 0) {
			status = 'empty';
		}
	});

	// Highlight selected node
	$effect(() => {
		if (!cy || !selectedId) return;
		cy.nodes().unselect();
		const node = cy.getElementById(selectedId);
		if (node.length > 0) node.select();
	});
</script>

<div class="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-[#0f172a]">
	<div bind:this={containerEl} class="absolute inset-0"></div>

	{#if status === 'loading'}
		<div class="pointer-events-none absolute inset-0 flex items-center justify-center">
			<div class="flex flex-col items-center gap-2 text-center">
				<Loader2 size={20} class="animate-spin text-blue-400/60" />
				<span class="text-xs text-blue-300/50">Rendering graph...</span>
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
			<p class="text-sm text-danger">Graph render failed: {errorMsg}</p>
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
