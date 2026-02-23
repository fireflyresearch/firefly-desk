<!--
  KnowledgeGraphExplorer.svelte - Knowledge graph visualization and management.

  Provides a toggle between a SvelteFlow graph view (via FlowCanvas) and a
  grouped list view. Includes entity detail panel, search, entity type filter
  chips, stats overlay, minimap, dagre auto-layout, and CRUD operations.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Loader2,
		Network,
		List,
		Trash2,
		X,
		ChevronDown,
		ChevronRight,
		AlertCircle,
		Pencil,
		BarChart3,
		Filter
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import FlowCanvas from '$lib/components/flow/FlowCanvas.svelte';
	import { toFlowNodes, toFlowEdges, layoutDagre } from '$lib/components/flow/flow-utils.js';
	import type {
		FlowNode as FlowNodeType,
		FlowEdge as FlowEdgeType,
		GraphEntity,
		GraphRelation
	} from '$lib/components/flow/flow-types.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface GraphNeighborhood {
		entity: GraphEntity;
		neighbors: GraphEntity[];
		relations: GraphRelation[];
	}

	interface GraphStats {
		entity_count: number;
		relation_count: number;
		type_counts?: Record<string, number>;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let viewMode = $state<'graph' | 'list'>('graph');
	let entities = $state<GraphEntity[]>([]);
	let relations = $state<GraphRelation[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');

	// Graph state (SvelteFlow)
	let flowNodes = $state<FlowNodeType[]>([]);
	let flowEdges = $state<FlowEdgeType[]>([]);

	// Entity type filter state
	let allEntityTypes = $state<string[]>([]);
	let hiddenTypes = $state<Set<string>>(new Set());

	// Stats
	let stats = $state<GraphStats | null>(null);
	let showStats = $state(true);

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
		let result = entities;

		// Apply search filter
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(
				(e) =>
					e.name.toLowerCase().includes(q) ||
					e.type.toLowerCase().includes(q)
			);
		}

		// Apply entity type filter
		if (hiddenTypes.size > 0) {
			result = result.filter((e) => !hiddenTypes.has(e.type.toLowerCase()));
		}

		return result;
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
	// Build flow graph from filtered data
	// -----------------------------------------------------------------------

	$effect(() => {
		if (filteredEntities.length === 0) {
			flowNodes = [];
			flowEdges = [];
			return;
		}

		const filteredIds = new Set(filteredEntities.map((e) => e.id));

		// Filter relations to only include those between visible entities
		const visibleRelations = relations.filter(
			(r) => filteredIds.has(r.source_id) && filteredIds.has(r.target_id)
		);

		// Convert to SvelteFlow nodes/edges
		const rawNodes = toFlowNodes(filteredEntities);
		const rawEdges = toFlowEdges(visibleRelations);

		// Apply dagre layout
		flowNodes = layoutDagre(rawNodes, rawEdges, {
			nodeWidth: 200,
			nodeHeight: 60,
			horizontalGap: 60,
			verticalGap: 80,
			direction: 'TB'
		});

		// Apply marker ends for directional arrows
		flowEdges = rawEdges.map((edge) => ({
			...edge,
			markerEnd: 'arrowclosed'
		}));

		// Highlight search matches by setting status to 'active'
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			flowNodes = flowNodes.map((node) => {
				const isMatch =
					node.data.label.toLowerCase().includes(q) ||
					(node.data.subtitle?.toLowerCase().includes(q) ?? false);
				if (isMatch) {
					return {
						...node,
						data: { ...node.data, status: 'active' as const }
					};
				}
				return node;
			});
		}
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadEntities() {
		loading = true;
		error = '';
		try {
			entities = await apiJson<GraphEntity[]>('/knowledge/graph/entities');

			// Extract unique entity types for filter chips
			const types = new Set<string>();
			for (const e of entities) {
				types.add(e.type.toLowerCase());
			}
			allEntityTypes = [...types].sort();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load entities';
		} finally {
			loading = false;
		}
	}

	async function loadRelations() {
		// Fetch neighborhoods for entities to gather relations
		const sampleSize = Math.min(entities.length, 50);
		const sampleEntities = entities.slice(0, sampleSize);

		const seenLinks = new Set<string>();
		const nodeIdSet = new Set(entities.map((e) => e.id));
		const collectedRelations: GraphRelation[] = [];

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
					collectedRelations.push(rel);
				}
			}
		} catch {
			// Relations are optional -- graph still works without them
		}

		relations = collectedRelations;
	}

	async function loadStats() {
		try {
			stats = await apiJson<GraphStats>('/knowledge/graph/stats');
		} catch {
			// Stats are non-critical; silently ignore errors
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
		loadEntities().then(() => {
			loadRelations();
			loadStats();
		});
	});

	// -----------------------------------------------------------------------
	// Node click handler -- bridge from FlowCanvas to entity detail
	// -----------------------------------------------------------------------

	function handleNodeClick(node: FlowNodeType) {
		const entity = entities.find((e) => e.id === node.id);
		if (entity) {
			selectEntity(entity);
		}
	}

	function handlePaneClick() {
		// Clicking the empty canvas clears selection
		closeDetail();
	}

	// -----------------------------------------------------------------------
	// Entity type filter
	// -----------------------------------------------------------------------

	function toggleTypeFilter(type: string) {
		const next = new Set(hiddenTypes);
		if (next.has(type)) {
			next.delete(type);
		} else {
			next.add(type);
		}
		hiddenTypes = next;
	}

	function showAllTypes() {
		hiddenTypes = new Set();
	}

	function hideAllTypes() {
		hiddenTypes = new Set(allEntityTypes);
	}

	// -----------------------------------------------------------------------
	// Entity selection and detail
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

	async function saveEntity() {
		if (!selectedEntity) return;
		savingEntity = true;
		error = '';
		try {
			await apiFetch(`/knowledge/graph/entities/${selectedEntity.id}`, {
				method: 'PATCH',
				body: JSON.stringify(editForm)
			});
			editingEntity = false;
			closeDetail();
			await loadEntities();
			await loadRelations();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save entity';
		} finally {
			savingEntity = false;
		}
	}

	async function deleteEntity(id: string) {
		if (!confirm('Delete this entity? This cannot be undone.')) return;
		error = '';
		try {
			await apiFetch(`/knowledge/graph/entities/${id}`, { method: 'DELETE' });
			closeDetail();
			await loadEntities();
			await loadRelations();
			await loadStats();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete entity';
		}
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

		<!-- Stats toggle -->
		<button
			type="button"
			onclick={() => (showStats = !showStats)}
			class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium transition-colors
				{showStats ? 'bg-accent/10 text-accent border-accent/30' : 'text-text-secondary hover:bg-surface-hover'}"
			title="Toggle Stats"
		>
			<BarChart3 size={14} />
		</button>

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

	<!-- Entity type filter chips -->
	{#if allEntityTypes.length > 0}
		<div class="flex items-center gap-2 overflow-x-auto">
			<Filter size={12} class="flex-shrink-0 text-text-secondary" />
			<button
				type="button"
				onclick={showAllTypes}
				class="flex-shrink-0 rounded-full border border-border px-2 py-0.5 text-xs font-medium transition-colors
					{hiddenTypes.size === 0 ? 'bg-accent/10 text-accent border-accent/30' : 'text-text-secondary hover:bg-surface-hover'}"
			>
				All
			</button>
			{#each allEntityTypes as type}
				<button
					type="button"
					onclick={() => toggleTypeFilter(type)}
					class="flex flex-shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize transition-colors
						{hiddenTypes.has(type)
						? 'border-border text-text-secondary/50 bg-surface-secondary/50 line-through'
						: 'border-border text-text-secondary hover:bg-surface-hover'}"
				>
					<span
						class="inline-block h-2 w-2 rounded-full"
						style="background-color: {getTypeColor(type)}{hiddenTypes.has(type) ? '40' : ''}"
					></span>
					{type}
				</button>
			{/each}
		</div>
	{/if}

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
					{#if filteredEntities.length === 0}
						<div
							class="absolute inset-0 flex flex-col items-center justify-center text-text-secondary"
						>
							<Network size={48} strokeWidth={1} class="mb-2 opacity-30" />
							<p class="text-sm">No entities in the knowledge graph.</p>
							<p class="text-xs">Documents with extracted entities will appear here.</p>
						</div>
					{:else}
						<FlowCanvas
							nodes={flowNodes}
							edges={flowEdges}
							fitView={true}
							interactive={true}
							options={{
								minimap: true,
								controls: true,
								background: 'dots',
								minZoom: 0.1,
								maxZoom: 5
							}}
							onNodeClick={handleNodeClick}
							onPaneClick={handlePaneClick}
						/>
					{/if}

					<!-- Stats overlay -->
					{#if showStats && stats}
						<div
							class="pointer-events-none absolute top-3 right-3 flex gap-2"
						>
							<div class="pointer-events-auto rounded-md border border-border bg-surface/90 px-3 py-2 text-xs shadow-sm backdrop-blur-sm">
								<div class="font-medium text-text-secondary">Entities</div>
								<div class="text-lg font-semibold text-text-primary">{stats.entity_count}</div>
							</div>
							<div class="pointer-events-auto rounded-md border border-border bg-surface/90 px-3 py-2 text-xs shadow-sm backdrop-blur-sm">
								<div class="font-medium text-text-secondary">Relations</div>
								<div class="text-lg font-semibold text-text-primary">{stats.relation_count}</div>
							</div>
						</div>
					{/if}

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
									{#if editingEntity}
										<div class="flex flex-col gap-2">
											<input
												type="text"
												bind:value={editForm.name}
												placeholder="Entity name"
												class="w-full rounded-md border border-border bg-surface py-1 px-2 text-sm text-text-primary outline-none focus:border-accent"
											/>
											<input
												type="text"
												bind:value={editForm.type}
												placeholder="Entity type"
												class="w-full rounded-md border border-border bg-surface py-1 px-2 text-sm text-text-primary outline-none focus:border-accent"
											/>
											<div class="flex gap-2">
												<button
													type="button"
													onclick={saveEntity}
													disabled={savingEntity}
													class="inline-flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
												>
													{#if savingEntity}
														<Loader2 size={12} class="animate-spin" />
													{/if}
													Save
												</button>
												<button
													type="button"
													onclick={() => (editingEntity = false)}
													class="rounded-md border border-border px-3 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
												>
													Cancel
												</button>
											</div>
										</div>
									{:else}
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
									{/if}
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
