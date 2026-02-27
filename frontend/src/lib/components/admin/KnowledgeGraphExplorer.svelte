<!--
  KnowledgeGraphExplorer.svelte - Orchestrator for the Knowledge Graph Explorer.

  Manages shared state, data loading, and composes sub-components:
  KGToolbar, KGFilterSidebar, KGGraphViewport, KGDetailPanel.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { slide } from 'svelte/transition';
	import { Loader2, AlertCircle } from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import type { GraphEntity, GraphRelation } from '$lib/components/flow/flow-types.js';
	import KGToolbar from './KGToolbar.svelte';
	import KGFilterSidebar from './KGFilterSidebar.svelte';
	import KGGraphViewport from './KGGraphViewport.svelte';
	import KGDetailPanel from './KGDetailPanel.svelte';

	// -----------------------------------------------------------------------
	// Props from parent (for KG regeneration)
	// -----------------------------------------------------------------------

	interface Props {
		onRegenerate?: () => void;
		regenerating?: boolean;
		regenerateMessage?: string;
		regenerateProgress?: number;
	}

	let {
		onRegenerate,
		regenerating = false,
		regenerateMessage = '',
		regenerateProgress = 0
	}: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface GraphNeighborhood {
		entities: GraphEntity[];
		relations: GraphRelation[];
	}

	interface GraphStats {
		entity_count: number;
		relation_count: number;
		entity_types?: Record<string, number>;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let entities = $state<GraphEntity[]>([]);
	let relations = $state<GraphRelation[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Filter
	let showFilterPanel = $state(true);
	let hiddenTypes = $state<Set<string>>(new Set());

	// Stats
	let stats = $state<GraphStats | null>(null);

	// Selection / detail
	let selectedEntity = $state<GraphEntity | null>(null);
	let neighborhood = $state<GraphNeighborhood | null>(null);
	let loadingDetail = $state(false);

	// -----------------------------------------------------------------------
	// Constants — type colors shared by filter sidebar and graph viewport
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
		system: '#0ea5e9',
		service: '#a855f7',
		endpoint: '#f97316',
		role: '#84cc16',
		domain: '#22d3ee',
		data_object: '#fb923c',
		configuration: '#a3a3a3',
		interface: '#d946ef',
		section: '#64748b',
		page: '#f43f5e',
		api: '#0284c7',
		default: '#6b7280'
	};

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	/** Entity type counts sorted by count descending. */
	let typeCounts = $derived.by(() => {
		if (stats?.entity_types) {
			return Object.entries(stats.entity_types).sort((a, b) => b[1] - a[1]);
		}
		const counts: Record<string, number> = {};
		for (const e of entities) {
			const t = (e.type ?? 'unknown').toLowerCase();
			counts[t] = (counts[t] || 0) + 1;
		}
		return Object.entries(counts).sort((a, b) => b[1] - a[1]);
	});

	/** Entities visible after type filtering. */
	let filteredEntities = $derived.by(() => {
		if (hiddenTypes.size === 0) return entities;
		return entities.filter((e) => !hiddenTypes.has((e.type ?? '').toLowerCase()));
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadEntities() {
		try {
			entities = await apiJson<GraphEntity[]>('/knowledge/graph/entities?limit=500');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load entities';
		}
	}

	async function loadRelations() {
		try {
			relations = await apiJson<GraphRelation[]>('/knowledge/graph/relations?limit=2000');
		} catch {
			// Relations are optional — graph still renders without them
		}
	}

	async function loadStats() {
		try {
			stats = await apiJson<GraphStats>('/knowledge/graph/stats');
		} catch {
			// Stats are non-critical
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

	async function refreshGraph() {
		loading = true;
		error = '';
		try {
			await Promise.all([loadEntities(), loadRelations(), loadStats()]);
		} finally {
			loading = false;
		}
	}

	// Initial load
	$effect(() => {
		refreshGraph();
	});

	// Listen for KG recompute event (from regeneration)
	$effect(() => {
		function handleRecomputeDone() {
			refreshGraph();
		}
		window.addEventListener('kg-recompute-done', handleRecomputeDone);
		return () => window.removeEventListener('kg-recompute-done', handleRecomputeDone);
	});

	// -----------------------------------------------------------------------
	// Filter actions
	// -----------------------------------------------------------------------

	function toggleType(type: string) {
		const next = new Set(hiddenTypes);
		if (next.has(type)) next.delete(type);
		else next.add(type);
		hiddenTypes = next;
	}

	function showAllTypes() {
		hiddenTypes = new Set();
	}

	function hideAllTypes() {
		hiddenTypes = new Set(typeCounts.map(([t]) => t));
	}

	function showOnlyType(type: string) {
		const all = new Set(typeCounts.map(([t]) => t));
		all.delete(type);
		hiddenTypes = all;
	}

	// -----------------------------------------------------------------------
	// Entity actions
	// -----------------------------------------------------------------------

	function selectEntity(entity: GraphEntity) {
		selectedEntity = entity;
		loadNeighborhood(entity.id);
	}

	function closeDetail() {
		selectedEntity = null;
		neighborhood = null;
	}

	async function saveEntity(
		entityId: string,
		updates: { name: string; type: string; properties: string; confidence: number }
	) {
		error = '';
		try {
			const parsedProperties = JSON.parse(updates.properties);
			await apiFetch(`/knowledge/graph/entities/${entityId}`, {
				method: 'PATCH',
				body: JSON.stringify({
					name: updates.name,
					entity_type: updates.type,
					properties: parsedProperties,
					confidence: updates.confidence
				})
			});
			closeDetail();
			await refreshGraph();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save entity';
			throw e;
		}
	}

	async function deleteEntity(entityId: string) {
		if (!confirm('Delete this entity? This cannot be undone.')) return;
		error = '';
		try {
			await apiFetch(`/knowledge/graph/entities/${entityId}`, { method: 'DELETE' });
			closeDetail();
			await refreshGraph();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete entity';
		}
	}
</script>

<div class="flex h-full min-h-0 min-w-0 flex-col">
	<!-- Toolbar -->
	<KGToolbar
		{showFilterPanel}
		{regenerating}
		{regenerateMessage}
		{regenerateProgress}
		onToggleFilter={() => (showFilterPanel = !showFilterPanel)}
		onRefresh={refreshGraph}
		{onRegenerate}
	/>

	<!-- Error banner -->
	{#if error}
		<div class="flex shrink-0 items-center gap-2 border-b border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
			<AlertCircle size={14} />
			{error}
		</div>
	{/if}

	<!-- Main content area -->
	{#if loading}
		<div class="flex flex-1 items-center justify-center">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="relative flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-lg border border-border">
			<!-- Filter sidebar -->
			{#if showFilterPanel}
				<div transition:slide={{ axis: 'x', duration: 200 }}>
					<KGFilterSidebar
						{typeCounts}
						{hiddenTypes}
						{stats}
						filteredEntityCount={filteredEntities.length}
						{typeColors}
						onToggleType={toggleType}
						onShowAll={showAllTypes}
						onHideAll={hideAllTypes}
						onShowOnly={showOnlyType}
					/>
				</div>
			{/if}

			<!-- Graph viewport -->
			<KGGraphViewport
				entities={entities}
				relations={relations}
				{hiddenTypes}
				selectedId={selectedEntity?.id ?? null}
				{typeColors}
				onNodeSelect={selectEntity}
				onShowAllTypes={showAllTypes}
			/>

			<!-- Detail panel -->
			{#if selectedEntity}
				<KGDetailPanel
					entity={selectedEntity}
					{neighborhood}
					{loadingDetail}
					{typeColors}
					onClose={closeDetail}
					onSave={saveEntity}
					onDelete={deleteEntity}
					onSelectNeighbor={selectEntity}
				/>
			{/if}
		</div>
	{/if}
</div>
