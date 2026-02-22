<!--
  KnowledgeGraphExplorer.svelte - Knowledge graph visualization and management.

  Provides a toggle between a D3 force-directed graph view (HTML5 Canvas)
  and a grouped list view. Includes entity detail panel, search, and CRUD.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Loader2,
		Network,
		List,
		ZoomIn,
		ZoomOut,
		Maximize2,
		Trash2,
		Save,
		X,
		ChevronDown,
		ChevronRight,
		AlertCircle,
		Pencil
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import {
		forceSimulation,
		forceLink,
		forceManyBody,
		forceCenter,
		forceCollide,
		type SimulationNodeDatum,
		type SimulationLinkDatum
	} from 'd3-force';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface GraphEntity {
		id: string;
		name: string;
		type: string;
		properties: Record<string, unknown>;
		source_documents?: string[];
	}

	interface GraphRelation {
		id: string;
		source_id: string;
		target_id: string;
		label: string;
	}

	interface GraphNeighborhood {
		entity: GraphEntity;
		neighbors: GraphEntity[];
		relations: GraphRelation[];
	}

	interface GraphNode extends SimulationNodeDatum {
		id: string;
		name: string;
		type: string;
		properties: Record<string, unknown>;
		source_documents?: string[];
	}

	interface GraphLink extends SimulationLinkDatum<GraphNode> {
		id: string;
		label: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let viewMode = $state<'graph' | 'list'>('graph');
	let entities = $state<GraphEntity[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');

	// Graph state
	let canvasEl = $state<HTMLCanvasElement | null>(null);
	let simulation = $state<ReturnType<typeof forceSimulation<GraphNode, GraphLink>> | null>(null);
	let graphNodes = $state<GraphNode[]>([]);
	let graphLinks = $state<GraphLink[]>([]);
	let zoom = $state(1);
	let panX = $state(0);
	let panY = $state(0);
	let isPanning = $state(false);
	let lastMousePos = $state({ x: 0, y: 0 });
	let draggedNode = $state<GraphNode | null>(null);
	let hoveredNode = $state<GraphNode | null>(null);

	// Selection/detail state
	let selectedEntity = $state<GraphEntity | null>(null);
	let neighborhood = $state<GraphNeighborhood | null>(null);
	let loadingDetail = $state(false);
	let editingEntity = $state(false);
	let savingEntity = $state(false);
	let editForm = $state({ name: '', type: '' });

	// List view state
	let expandedTypes = $state<Set<string>>(new Set());

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const typeColors: Record<string, string> = {
		person: '#3b82f6',
		organization: '#8b5cf6',
		location: '#10b981',
		concept: '#f59e0b',
		technology: '#06b6d4',
		event: '#ef4444',
		document: '#6366f1',
		product: '#ec4899',
		process: '#14b8a6',
		default: '#6b7280'
	};

	function getTypeColor(type: string): string {
		return typeColors[type.toLowerCase()] ?? typeColors.default;
	}

	// -----------------------------------------------------------------------
	// Filtered data
	// -----------------------------------------------------------------------

	let filteredEntities = $derived.by(() => {
		if (!searchQuery.trim()) return entities;
		const q = searchQuery.toLowerCase();
		return entities.filter(
			(e) =>
				e.name.toLowerCase().includes(q) ||
				e.type.toLowerCase().includes(q)
		);
	});

	let entitiesByType = $derived.by(() => {
		const groups: Record<string, GraphEntity[]> = {};
		for (const entity of filteredEntities) {
			const type = entity.type || 'unknown';
			if (!groups[type]) groups[type] = [];
			groups[type].push(entity);
		}
		return groups;
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadEntities() {
		loading = true;
		error = '';
		try {
			entities = await apiJson<GraphEntity[]>('/knowledge/graph/entities');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load entities';
		} finally {
			loading = false;
		}
	}

	async function loadNeighborhood(entityId: string) {
		loadingDetail = true;
		try {
			neighborhood = await apiJson<GraphNeighborhood>(
				`/knowledge/graph/entities/${entityId}/neighborhood`
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load entity neighborhood';
		} finally {
			loadingDetail = false;
		}
	}

	$effect(() => {
		loadEntities();
	});

	// -----------------------------------------------------------------------
	// Graph initialization
	// -----------------------------------------------------------------------

	$effect(() => {
		if (viewMode !== 'graph' || !canvasEl || loading || entities.length === 0) return;

		// Build graph from entities -- try loading neighborhoods for relations
		buildGraph();
	});

	async function buildGraph() {
		// Use entities as nodes
		const nodes: GraphNode[] = entities.map((e) => ({
			id: e.id,
			name: e.name,
			type: e.type,
			properties: e.properties,
			source_documents: e.source_documents
		}));

		// Try to load relations from the stats/neighborhood endpoints
		const links: GraphLink[] = [];

		// Fetch neighborhoods for a sample of entities to get relations
		// For larger datasets, we only load a subset
		const sampleSize = Math.min(entities.length, 50);
		const sampleEntities = entities.slice(0, sampleSize);

		const seenLinks = new Set<string>();
		const nodeIdSet = new Set(entities.map((e) => e.id));

		try {
			const neighborhoods = await Promise.allSettled(
				sampleEntities.map((e) =>
					apiJson<GraphNeighborhood>(`/knowledge/graph/entities/${e.id}/neighborhood`)
				)
			);

			for (const result of neighborhoods) {
				if (result.status !== 'fulfilled') continue;
				const hood = result.value;
				for (const rel of hood.relations) {
					if (seenLinks.has(rel.id)) continue;
					if (!nodeIdSet.has(rel.source_id) || !nodeIdSet.has(rel.target_id)) continue;
					seenLinks.add(rel.id);
					links.push({
						id: rel.id,
						source: rel.source_id,
						target: rel.target_id,
						label: rel.label
					});
				}
			}
		} catch {
			// Relations are optional -- graph still works without them
		}

		graphNodes = nodes;
		graphLinks = links;

		initSimulation();
	}

	function initSimulation() {
		if (!canvasEl) return;

		const width = canvasEl.width;
		const height = canvasEl.height;

		// Stop existing simulation
		if (simulation) {
			simulation.stop();
		}

		const sim = forceSimulation<GraphNode, GraphLink>(graphNodes)
			.force(
				'link',
				forceLink<GraphNode, GraphLink>(graphLinks)
					.id((d) => d.id)
					.distance(80)
			)
			.force('charge', forceManyBody().strength(-200))
			.force('center', forceCenter(width / 2, height / 2))
			.force('collision', forceCollide(25))
			.on('tick', () => {
				drawGraph();
			});

		simulation = sim;
	}

	// -----------------------------------------------------------------------
	// Canvas rendering
	// -----------------------------------------------------------------------

	function drawGraph() {
		if (!canvasEl) return;
		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;

		const width = canvasEl.width;
		const height = canvasEl.height;

		ctx.clearRect(0, 0, width, height);
		ctx.save();
		ctx.translate(panX, panY);
		ctx.scale(zoom, zoom);

		// Draw links
		ctx.lineWidth = 1;
		ctx.strokeStyle = '#9ca3af';
		for (const link of graphLinks) {
			const source = link.source as GraphNode;
			const target = link.target as GraphNode;
			if (source.x == null || source.y == null || target.x == null || target.y == null) continue;

			ctx.beginPath();
			ctx.moveTo(source.x, source.y);
			ctx.lineTo(target.x, target.y);

			// Highlight links connected to selected node
			if (
				selectedEntity &&
				(source.id === selectedEntity.id || target.id === selectedEntity.id)
			) {
				ctx.strokeStyle = '#3b82f6';
				ctx.lineWidth = 2;
			} else {
				ctx.strokeStyle = '#9ca3af40';
				ctx.lineWidth = 1;
			}
			ctx.stroke();

			// Draw edge label
			if (link.label) {
				const mx = (source.x + target.x) / 2;
				const my = (source.y + target.y) / 2;
				ctx.font = '9px system-ui';
				ctx.fillStyle = '#9ca3af';
				ctx.textAlign = 'center';
				ctx.fillText(link.label, mx, my - 4);
			}
		}

		// Draw nodes
		for (const node of graphNodes) {
			if (node.x == null || node.y == null) continue;

			const color = getTypeColor(node.type);
			const isSelected = selectedEntity?.id === node.id;
			const isHovered = hoveredNode?.id === node.id;
			const isHighlighted =
				searchQuery.trim() &&
				(node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
					node.type.toLowerCase().includes(searchQuery.toLowerCase()));

			// Node circle
			const radius = isSelected ? 12 : isHovered ? 10 : 8;
			ctx.beginPath();
			ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
			ctx.fillStyle = color;
			ctx.fill();

			// Highlight ring
			if (isSelected || isHighlighted) {
				ctx.beginPath();
				ctx.arc(node.x, node.y, radius + 3, 0, Math.PI * 2);
				ctx.strokeStyle = isSelected ? '#3b82f6' : '#f59e0b';
				ctx.lineWidth = 2;
				ctx.stroke();
			}

			// Label
			ctx.font = isSelected ? 'bold 11px system-ui' : '10px system-ui';
			ctx.fillStyle = isSelected ? '#1f2937' : '#6b7280';
			ctx.textAlign = 'center';
			ctx.fillText(node.name, node.x, node.y + radius + 12);
		}

		ctx.restore();
	}

	// -----------------------------------------------------------------------
	// Canvas interactions
	// -----------------------------------------------------------------------

	function getNodeAtPosition(clientX: number, clientY: number): GraphNode | null {
		if (!canvasEl) return null;
		const rect = canvasEl.getBoundingClientRect();
		const x = (clientX - rect.left - panX) / zoom;
		const y = (clientY - rect.top - panY) / zoom;

		for (let i = graphNodes.length - 1; i >= 0; i--) {
			const node = graphNodes[i];
			if (node.x == null || node.y == null) continue;
			const dx = x - node.x;
			const dy = y - node.y;
			if (dx * dx + dy * dy < 15 * 15) {
				return node;
			}
		}
		return null;
	}

	function handleCanvasMouseDown(event: MouseEvent) {
		const node = getNodeAtPosition(event.clientX, event.clientY);
		if (node) {
			draggedNode = node;
			node.fx = node.x;
			node.fy = node.y;
			simulation?.alphaTarget(0.3).restart();
		} else {
			isPanning = true;
		}
		lastMousePos = { x: event.clientX, y: event.clientY };
	}

	function handleCanvasMouseMove(event: MouseEvent) {
		if (draggedNode) {
			if (!canvasEl) return;
			const rect = canvasEl.getBoundingClientRect();
			draggedNode.fx = (event.clientX - rect.left - panX) / zoom;
			draggedNode.fy = (event.clientY - rect.top - panY) / zoom;
		} else if (isPanning) {
			panX += event.clientX - lastMousePos.x;
			panY += event.clientY - lastMousePos.y;
			lastMousePos = { x: event.clientX, y: event.clientY };
			drawGraph();
		} else {
			// Hover detection
			hoveredNode = getNodeAtPosition(event.clientX, event.clientY);
			if (canvasEl) {
				canvasEl.style.cursor = hoveredNode ? 'pointer' : 'grab';
			}
			drawGraph();
		}
	}

	function handleCanvasMouseUp() {
		if (draggedNode) {
			draggedNode.fx = null;
			draggedNode.fy = null;
			simulation?.alphaTarget(0);
			draggedNode = null;
		}
		isPanning = false;
	}

	function handleCanvasClick(event: MouseEvent) {
		const node = getNodeAtPosition(event.clientX, event.clientY);
		if (node) {
			selectEntity({
				id: node.id,
				name: node.name,
				type: node.type,
				properties: node.properties,
				source_documents: node.source_documents
			});
		}
	}

	function handleCanvasWheel(event: WheelEvent) {
		event.preventDefault();
		const delta = event.deltaY > 0 ? 0.9 : 1.1;
		const newZoom = Math.max(0.1, Math.min(5, zoom * delta));

		// Zoom towards mouse position
		if (canvasEl) {
			const rect = canvasEl.getBoundingClientRect();
			const mx = event.clientX - rect.left;
			const my = event.clientY - rect.top;
			panX = mx - ((mx - panX) / zoom) * newZoom;
			panY = my - ((my - panY) / zoom) * newZoom;
		}

		zoom = newZoom;
		drawGraph();
	}

	// Resize canvas to fit container
	$effect(() => {
		if (!canvasEl) return;
		const observer = new ResizeObserver((entries) => {
			for (const entry of entries) {
				if (canvasEl) {
					canvasEl.width = entry.contentRect.width;
					canvasEl.height = entry.contentRect.height;
					drawGraph();
				}
			}
		});
		observer.observe(canvasEl.parentElement!);
		return () => observer.disconnect();
	});

	// -----------------------------------------------------------------------
	// Entity selection & detail
	// -----------------------------------------------------------------------

	function selectEntity(entity: GraphEntity) {
		selectedEntity = entity;
		editingEntity = false;
		loadNeighborhood(entity.id);
	}

	function closeDetail() {
		selectedEntity = null;
		neighborhood = null;
		editingEntity = false;
	}

	function startEditEntity() {
		if (!selectedEntity) return;
		editForm = {
			name: selectedEntity.name,
			type: selectedEntity.type
		};
		editingEntity = true;
	}

	async function deleteEntity(id: string) {
		if (!confirm('Delete this entity? This cannot be undone.')) return;
		error = '';
		try {
			await apiFetch(`/knowledge/graph/entities/${id}`, { method: 'DELETE' });
			closeDetail();
			await loadEntities();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete entity';
		}
	}

	// -----------------------------------------------------------------------
	// Zoom controls
	// -----------------------------------------------------------------------

	function zoomIn() {
		zoom = Math.min(5, zoom * 1.2);
		drawGraph();
	}

	function zoomOut() {
		zoom = Math.max(0.1, zoom / 1.2);
		drawGraph();
	}

	function resetView() {
		zoom = 1;
		panX = 0;
		panY = 0;
		drawGraph();
	}

	// -----------------------------------------------------------------------
	// List view toggle
	// -----------------------------------------------------------------------

	function toggleTypeGroup(type: string) {
		const next = new Set(expandedTypes);
		if (next.has(type)) {
			next.delete(type);
		} else {
			next.add(type);
		}
		expandedTypes = next;
	}
</script>

<div class="flex h-full flex-col gap-3">
	<!-- Toolbar -->
	<div class="flex items-center gap-3">
		<!-- Search -->
		<div class="relative flex-1">
			<Search size={14} class="absolute top-1/2 left-3 -translate-y-1/2 text-text-secondary" />
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search entities..."
				class="w-full rounded-md border border-border bg-surface py-1.5 pr-3 pl-8 text-sm text-text-primary outline-none focus:border-accent"
			/>
		</div>

		<!-- View toggle -->
		<div class="flex rounded-md border border-border">
			<button
				type="button"
				onclick={() => (viewMode = 'graph')}
				class="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium transition-colors
					{viewMode === 'graph'
					? 'bg-accent text-white'
					: 'text-text-secondary hover:bg-surface-hover'}"
				title="Graph View"
			>
				<Network size={14} />
				Graph
			</button>
			<button
				type="button"
				onclick={() => (viewMode = 'list')}
				class="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium transition-colors
					{viewMode === 'list'
					? 'bg-accent text-white'
					: 'text-text-secondary hover:bg-surface-hover'}"
				title="List View"
			>
				<List size={14} />
				List
			</button>
		</div>
	</div>

	<!-- Error banner -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<AlertCircle size={16} />
			{error}
		</div>
	{/if}

	<!-- Content area -->
	{#if loading}
		<div class="flex flex-1 items-center justify-center">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="flex flex-1 gap-3 overflow-hidden">
			<!-- ============================================================= -->
			<!-- Graph View                                                     -->
			<!-- ============================================================= -->
			{#if viewMode === 'graph'}
				<div class="relative flex-1 overflow-hidden rounded-lg border border-border bg-surface">
					<canvas
						bind:this={canvasEl}
						onmousedown={handleCanvasMouseDown}
						onmousemove={handleCanvasMouseMove}
						onmouseup={handleCanvasMouseUp}
						onclick={handleCanvasClick}
						onwheel={handleCanvasWheel}
						onmouseleave={() => {
							isPanning = false;
							draggedNode = null;
							hoveredNode = null;
						}}
						class="block h-full w-full"
						style="cursor: grab"
					></canvas>

					<!-- Zoom controls -->
					<div
						class="absolute top-3 right-3 flex flex-col gap-1 rounded-md border border-border bg-surface shadow-sm"
					>
						<button
							type="button"
							onclick={zoomIn}
							class="rounded-t-md p-1.5 text-text-secondary hover:bg-surface-hover"
							title="Zoom In"
						>
							<ZoomIn size={14} />
						</button>
						<button
							type="button"
							onclick={zoomOut}
							class="p-1.5 text-text-secondary hover:bg-surface-hover"
							title="Zoom Out"
						>
							<ZoomOut size={14} />
						</button>
						<button
							type="button"
							onclick={resetView}
							class="rounded-b-md p-1.5 text-text-secondary hover:bg-surface-hover"
							title="Reset View"
						>
							<Maximize2 size={14} />
						</button>
					</div>

					<!-- Legend -->
					<div class="absolute bottom-3 left-3 rounded-md border border-border bg-surface/90 p-2 text-xs backdrop-blur-sm">
						<div class="mb-1 font-medium text-text-secondary">Entity Types</div>
						<div class="flex flex-wrap gap-2">
							{#each Object.entries(entitiesByType) as [type]}
								<div class="flex items-center gap-1">
									<span
										class="inline-block h-2.5 w-2.5 rounded-full"
										style="background-color: {getTypeColor(type)}"
									></span>
									<span class="capitalize text-text-secondary">{type}</span>
								</div>
							{/each}
						</div>
					</div>

					<!-- Empty state -->
					{#if entities.length === 0}
						<div
							class="absolute inset-0 flex flex-col items-center justify-center text-text-secondary"
						>
							<Network size={48} strokeWidth={1} class="mb-2 opacity-30" />
							<p class="text-sm">No entities in the knowledge graph.</p>
							<p class="text-xs">Documents with extracted entities will appear here.</p>
						</div>
					{/if}
				</div>

			<!-- ============================================================= -->
			<!-- List View                                                      -->
			<!-- ============================================================= -->
			{:else}
				<div class="flex-1 overflow-y-auto">
					{#if Object.keys(entitiesByType).length === 0}
						<div class="flex flex-col items-center justify-center py-12 text-text-secondary">
							<Network size={48} strokeWidth={1} class="mb-2 opacity-30" />
							<p class="text-sm">No entities found.</p>
						</div>
					{:else}
						<div class="flex flex-col gap-2">
							{#each Object.entries(entitiesByType).sort((a, b) => a[0].localeCompare(b[0])) as [type, typeEntities]}
								<div class="rounded-lg border border-border bg-surface">
									<!-- Group header -->
									<button
										type="button"
										onclick={() => toggleTypeGroup(type)}
										class="flex w-full items-center gap-2 px-4 py-2.5 text-left transition-colors hover:bg-surface-secondary/50"
									>
										{#if expandedTypes.has(type)}
											<ChevronDown size={14} class="text-text-secondary" />
										{:else}
											<ChevronRight size={14} class="text-text-secondary" />
										{/if}
										<span
											class="inline-block h-2.5 w-2.5 rounded-full"
											style="background-color: {getTypeColor(type)}"
										></span>
										<span class="text-sm font-medium capitalize text-text-primary">
											{type}
										</span>
										<span
											class="rounded-full bg-surface-secondary px-2 py-0.5 text-xs text-text-secondary"
										>
											{typeEntities.length}
										</span>
									</button>

									<!-- Expanded entity cards -->
									{#if expandedTypes.has(type)}
										<div class="border-t border-border px-4 py-2">
											<div class="flex flex-col gap-1.5">
												{#each typeEntities as entity}
													<button
														type="button"
														onclick={() => selectEntity(entity)}
														class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors hover:bg-surface-secondary/50
															{selectedEntity?.id === entity.id ? 'bg-accent/5 ring-1 ring-accent/30' : ''}"
													>
														<span class="text-sm font-medium text-text-primary">
															{entity.name}
														</span>
														{#if entity.properties && Object.keys(entity.properties).length > 0}
															<span class="text-xs text-text-secondary">
																{Object.keys(entity.properties).length} properties
															</span>
														{/if}
														{#if entity.source_documents && entity.source_documents.length > 0}
															<span class="text-xs text-text-secondary">
																{entity.source_documents.length} source{entity.source_documents
																	.length !== 1
																	? 's'
																	: ''}
															</span>
														{/if}
													</button>
												{/each}
											</div>
										</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<!-- ============================================================= -->
			<!-- Detail Panel (shared between views)                            -->
			<!-- ============================================================= -->
			{#if selectedEntity}
				<div
					class="flex w-80 shrink-0 flex-col rounded-lg border border-border bg-surface"
				>
					<!-- Panel header -->
					<div class="flex items-center justify-between border-b border-border px-3 py-2.5">
						<h4 class="text-sm font-semibold text-text-primary">Entity Detail</h4>
						<div class="flex items-center gap-1">
							<button
								type="button"
								onclick={startEditEntity}
								class="rounded p-1 text-text-secondary hover:bg-accent/10 hover:text-accent"
								title="Edit"
							>
								<Pencil size={12} />
							</button>
							<button
								type="button"
								onclick={() => deleteEntity(selectedEntity!.id)}
								class="rounded p-1 text-text-secondary hover:bg-danger/10 hover:text-danger"
								title="Delete"
							>
								<Trash2 size={12} />
							</button>
							<button
								type="button"
								onclick={closeDetail}
								class="rounded p-1 text-text-secondary hover:text-text-primary"
								title="Close"
							>
								<X size={12} />
							</button>
						</div>
					</div>

					<!-- Panel body -->
					<div class="flex-1 overflow-y-auto p-3">
						{#if loadingDetail}
							<div class="flex items-center justify-center py-8">
								<Loader2 size={16} class="animate-spin text-text-secondary" />
							</div>
						{:else}
							<div class="flex flex-col gap-3">
								<!-- Name and type -->
								<div>
									<h5 class="text-sm font-semibold text-text-primary">
										{selectedEntity.name}
									</h5>
									<span
										class="mt-0.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium capitalize"
										style="background-color: {getTypeColor(selectedEntity.type)}20; color: {getTypeColor(selectedEntity.type)}"
									>
										<span
											class="inline-block h-1.5 w-1.5 rounded-full"
											style="background-color: {getTypeColor(selectedEntity.type)}"
										></span>
										{selectedEntity.type}
									</span>
								</div>

								<!-- Properties -->
								{#if selectedEntity.properties && Object.keys(selectedEntity.properties).length > 0}
									<div>
										<h6 class="mb-1 text-xs font-medium text-text-secondary">Properties</h6>
										<div class="rounded-md border border-border bg-surface-secondary p-2">
											{#each Object.entries(selectedEntity.properties) as [key, value]}
												<div class="flex items-start gap-2 py-0.5 text-xs">
													<span class="font-medium text-text-secondary">{key}:</span>
													<span class="text-text-primary">{String(value)}</span>
												</div>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Related entities -->
								{#if neighborhood?.neighbors && neighborhood.neighbors.length > 0}
									<div>
										<h6 class="mb-1 text-xs font-medium text-text-secondary">
											Related Entities ({neighborhood.neighbors.length})
										</h6>
										<div class="flex flex-col gap-1">
											{#each neighborhood.neighbors as neighbor}
												<button
													type="button"
													onclick={() => selectEntity(neighbor)}
													class="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-surface-secondary"
												>
													<span
														class="inline-block h-2 w-2 rounded-full"
														style="background-color: {getTypeColor(neighbor.type)}"
													></span>
													<span class="font-medium text-text-primary">{neighbor.name}</span>
													<span class="capitalize text-text-secondary">{neighbor.type}</span>
												</button>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Relations -->
								{#if neighborhood?.relations && neighborhood.relations.length > 0}
									<div>
										<h6 class="mb-1 text-xs font-medium text-text-secondary">
											Relations ({neighborhood.relations.length})
										</h6>
										<div class="flex flex-col gap-1">
											{#each neighborhood.relations as rel}
												<div
													class="rounded-md border border-border bg-surface-secondary px-2 py-1.5 text-xs"
												>
													<span class="font-medium text-accent">{rel.label}</span>
												</div>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Source documents -->
								{#if selectedEntity.source_documents && selectedEntity.source_documents.length > 0}
									<div>
										<h6 class="mb-1 text-xs font-medium text-text-secondary">
											Source Documents ({selectedEntity.source_documents.length})
										</h6>
										<div class="flex flex-col gap-1">
											{#each selectedEntity.source_documents as docId}
												<div
													class="rounded-md bg-surface-secondary px-2 py-1 font-mono text-xs text-text-secondary"
												>
													{docId}
												</div>
											{/each}
										</div>
									</div>
								{/if}
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
