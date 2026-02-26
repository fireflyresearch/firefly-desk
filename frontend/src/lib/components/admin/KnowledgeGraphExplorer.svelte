<!--
  KnowledgeGraphExplorer.svelte - Knowledge graph visualization and management.

  3D WebGL force-directed graph (via 3d-force-graph / Three.js) designed for
  large graphs (hundreds of nodes). Features: collapsible filter sidebar with
  type counts, orbit/zoom/pan, ground grid with axis indicators, node type
  labels, entity detail/edit slide-out panel, stats overlay, and CRUD
  operations. All panels contained within the parent flex container — no
  width overflow.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import { fly, slide } from 'svelte/transition';
	import {
		Loader2,
		Network,
		Trash2,
		X,
		AlertCircle,
		Pencil,
		Filter,
		Save,
		Check,
		RefreshCw,
		Maximize2,
		PanelLeftClose,
		PanelLeft,
		Sparkles
	} from 'lucide-svelte';
	import * as THREE from 'three';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import type { GraphEntity, GraphRelation } from '$lib/components/flow/flow-types.js';

	// Props from parent for KG regeneration
	interface Props {
		onRegenerate?: () => void;
		regenerating?: boolean;
		regenerateMessage?: string;
		regenerateProgress?: number;
	}

	let { onRegenerate, regenerating = false, regenerateMessage = '', regenerateProgress = 0 }: Props = $props();

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

	interface EntityEditForm {
		name: string;
		type: string;
		properties: string;
		confidence: number;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let entities = $state<GraphEntity[]>([]);
	let relations = $state<GraphRelation[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Filter sidebar
	let showFilterPanel = $state(true);
	let hiddenTypes = $state<Set<string>>(new Set());
	let filterSearch = $state('');

	// Stats (from API — gives accurate counts without fetching all entities)
	let stats = $state<GraphStats | null>(null);

	// Selection/detail state
	let selectedEntity = $state<GraphEntity | null>(null);
	let neighborhood = $state<GraphNeighborhood | null>(null);
	let loadingDetail = $state(false);
	let editingEntity = $state(false);
	let savingEntity = $state(false);
	let editForm = $state<EntityEditForm>({
		name: '',
		type: '',
		properties: '{}',
		confidence: 1.0
	});
	let propertiesJsonError = $state('');

	// 3D graph refs
	let graphInstance: any = null;
	let graphContainerEl: HTMLDivElement;
	let containerEl: HTMLDivElement;

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

	function getTypeColor(type: string): string {
		return typeColors[(type ?? '').toLowerCase()] ?? typeColors.default;
	}

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let editFormModified = $derived.by(() => {
		if (!selectedEntity || !editingEntity) return false;
		if (editForm.name !== selectedEntity.name) return true;
		if (editForm.type !== selectedEntity.type) return true;
		if (editForm.confidence !== (selectedEntity.confidence ?? 1.0)) return true;
		const originalJson = JSON.stringify(selectedEntity.properties ?? {}, null, 2);
		if (editForm.properties.trim() !== originalJson) return true;
		return false;
	});

	/** All entity types with their counts, sorted by count descending. */
	let typeCounts = $derived.by(() => {
		// Prefer stats from API (accurate even if entities are capped)
		if (stats?.entity_types) {
			return Object.entries(stats.entity_types)
				.sort((a, b) => b[1] - a[1]);
		}
		// Fallback to local entity data
		const counts: Record<string, number> = {};
		for (const e of entities) {
			const t = (e.type ?? 'unknown').toLowerCase();
			counts[t] = (counts[t] || 0) + 1;
		}
		return Object.entries(counts).sort((a, b) => b[1] - a[1]);
	});

	/** Filtered type list for the sidebar search. */
	let filteredTypeCounts = $derived.by(() => {
		if (!filterSearch.trim()) return typeCounts;
		const q = filterSearch.toLowerCase();
		return typeCounts.filter(([type]) => type.includes(q));
	});

	let filteredEntities = $derived.by(() => {
		let result = entities;
		if (hiddenTypes.size > 0) {
			result = result.filter((e) => !hiddenTypes.has((e.type ?? '').toLowerCase()));
		}
		return result;
	});

	/** Number of visible types (not hidden). */
	let visibleTypeCount = $derived(typeCounts.length - hiddenTypes.size);

	// -----------------------------------------------------------------------
	// 3D Force Graph
	// -----------------------------------------------------------------------

	async function buildGraph3D() {
		if (!containerEl) return;

		// Clear previous instance
		if (graphInstance) {
			graphInstance._destructor?.();
			graphInstance = null;
		}
		// Also clear any leftover children from previous instance
		if (graphContainerEl) {
			while (graphContainerEl.firstChild) {
				graphContainerEl.removeChild(graphContainerEl.firstChild);
			}
		}

		if (filteredEntities.length === 0) return;

		const rect = containerEl.getBoundingClientRect();
		if (rect.width === 0 || rect.height === 0) return;

		const filteredIds = new Set(filteredEntities.map((e) => e.id));

		const nodes = filteredEntities.map((e) => ({
			id: e.id,
			name: e.name ?? 'Unnamed',
			type: (e.type ?? 'unknown').toLowerCase(),
			entity: e
		}));

		const visibleRelations = relations.filter(
			(r) => filteredIds.has(r.source_id) && filteredIds.has(r.target_id)
		);

		const nodeIdSet = new Set(nodes.map((n) => n.id));
		const links = visibleRelations
			.filter((r) => nodeIdSet.has(r.source_id) && nodeIdSet.has(r.target_id))
			.map((r) => ({
				source: r.source_id,
				target: r.target_id,
				label: r.label || r.relation_type,
				relation: r
			}));

		// Dynamic import to avoid SSR issues
		const ForceGraph3DModule = await import('3d-force-graph');
		const ForceGraph3D = ForceGraph3DModule.default as any;

		graphInstance = ForceGraph3D()(graphContainerEl)
			.width(rect.width)
			.height(rect.height)
			.backgroundColor('rgba(0,0,0,0)')
			.graphData({ nodes, links })
			.nodeId('id')
			.nodeLabel((node: any) => `<b>${node.name}</b><br/><span style="color:${getTypeColor(node.type)}">${node.type}</span>`)
			.nodeThreeObject((node: any) => {
				const group = new THREE.Group();

				// Sphere
				const geometry = new THREE.SphereGeometry(4, 16, 16);
				const material = new THREE.MeshLambertMaterial({ color: getTypeColor(node.type) });
				const sphere = new THREE.Mesh(geometry, material);
				group.add(sphere);

				// Type label sprite
				const canvas = document.createElement('canvas');
				canvas.width = 128;
				canvas.height = 32;
				const ctx = canvas.getContext('2d')!;
				ctx.font = '14px sans-serif';
				ctx.fillStyle = getTypeColor(node.type);
				ctx.textAlign = 'center';
				ctx.fillText(node.type, 64, 22);
				const texture = new THREE.CanvasTexture(canvas);
				const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.8 });
				const sprite = new THREE.Sprite(spriteMat);
				sprite.scale.set(12, 3, 1);
				sprite.position.y = 6;
				group.add(sprite);

				return group;
			})
			.nodeThreeObjectExtend(false)
			.linkSource('source')
			.linkTarget('target')
			.linkColor(() => 'rgba(156,163,175,0.6)')
			.linkWidth(1.5)
			.linkDirectionalArrowLength(4)
			.linkDirectionalArrowRelPos(1)
			.onNodeClick((node: any) => {
				if (node.entity) {
					selectEntity(node.entity);
				}
			})
			.onNodeHover((node: any) => {
				if (graphContainerEl) {
					graphContainerEl.style.cursor = node ? 'pointer' : 'default';
				}
			});

		// Access the Three.js scene
		const scene = graphInstance.scene();

		// Ground grid — subtle reference plane
		const gridHelper = new THREE.GridHelper(200, 20, 0x444444, 0x333333);
		gridHelper.position.y = -50;
		const gridMaterials = Array.isArray(gridHelper.material)
			? gridHelper.material
			: [gridHelper.material];
		for (const mat of gridMaterials) {
			mat.opacity = 0.15;
			mat.transparent = true;
		}
		scene.add(gridHelper);

		// Axis lines — subtle colored indicators
		const axisLength = 60;
		const axisMaterial = (color: number) => new THREE.LineBasicMaterial({ color, opacity: 0.4, transparent: true });
		// X axis (red)
		const xGeom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-axisLength, -50, 0), new THREE.Vector3(axisLength, -50, 0)]);
		scene.add(new THREE.Line(xGeom, axisMaterial(0xff4444)));
		// Z axis (blue)
		const zGeom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -50, -axisLength), new THREE.Vector3(0, -50, axisLength)]);
		scene.add(new THREE.Line(zGeom, axisMaterial(0x4444ff)));
	}

	function clearHighlight() {
		/* 3D graph handles highlighting internally */
	}

	// Rebuild graph when data changes
	let graphVersion = $state(0);
	$effect(() => {
		void filteredEntities;
		void relations;
		void graphVersion;

		if (!loading && filteredEntities.length > 0) {
			tick().then(() => buildGraph3D());
		}
	});

	// Resize handler
	$effect(() => {
		if (!containerEl) return;
		let debounce: ReturnType<typeof setTimeout>;
		const observer = new ResizeObserver(() => {
			clearTimeout(debounce);
			debounce = setTimeout(() => {
				if (graphInstance && containerEl) {
					const rect = containerEl.getBoundingClientRect();
					graphInstance.width(rect.width).height(rect.height);
				}
			}, 200);
		});
		observer.observe(containerEl);
		return () => {
			observer.disconnect();
			clearTimeout(debounce);
		};
	});

	// Cleanup on destroy
	$effect(() => {
		return () => {
			if (graphInstance) {
				graphInstance._destructor?.();
				graphInstance = null;
			}
		};
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadEntities() {
		loading = true;
		error = '';
		try {
			entities = await apiJson<GraphEntity[]>('/knowledge/graph/entities?limit=500');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load entities';
		} finally {
			loading = false;
		}
	}

	async function loadRelations() {
		const sampleSize = Math.min(entities.length, 200);
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
				for (const rel of result.value.relations) {
					if (seenLinks.has(rel.id)) continue;
					if (!nodeIdSet.has(rel.source_id) || !nodeIdSet.has(rel.target_id)) continue;
					seenLinks.add(rel.id);
					collectedRelations.push(rel);
				}
			}
		} catch {
			// Relations are optional
		}

		relations = collectedRelations;
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
		await loadEntities();
		await Promise.all([loadRelations(), loadStats()]);
		graphVersion++;
	}

	$effect(() => {
		function handleRecomputeDone() {
			refreshGraph();
		}
		window.addEventListener('kg-recompute-done', handleRecomputeDone);
		return () => window.removeEventListener('kg-recompute-done', handleRecomputeDone);
	});

	$effect(() => {
		loadEntities().then(() => {
			loadRelations();
			loadStats();
		});
	});

	// -----------------------------------------------------------------------
	// Filter actions
	// -----------------------------------------------------------------------

	function toggleTypeFilter(type: string) {
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
	// Entity selection and detail
	// -----------------------------------------------------------------------

	function selectEntity(entity: GraphEntity) {
		selectedEntity = entity;
		editingEntity = false;
		propertiesJsonError = '';
		loadNeighborhood(entity.id);
	}

	function closeDetail() {
		selectedEntity = null;
		neighborhood = null;
		editingEntity = false;
		propertiesJsonError = '';
		clearHighlight();
	}

	function startEditEntity() {
		if (!selectedEntity) return;
		editForm = {
			name: selectedEntity.name,
			type: selectedEntity.type,
			properties: JSON.stringify(selectedEntity.properties ?? {}, null, 2),
			confidence: selectedEntity.confidence ?? 1.0
		};
		propertiesJsonError = '';
		editingEntity = true;
	}

	function cancelEdit() {
		editingEntity = false;
		propertiesJsonError = '';
	}

	function validatePropertiesJson(value: string): boolean {
		try {
			JSON.parse(value);
			propertiesJsonError = '';
			return true;
		} catch {
			propertiesJsonError = 'Invalid JSON';
			return false;
		}
	}

	async function saveEntity() {
		if (!selectedEntity) return;
		if (!validatePropertiesJson(editForm.properties)) return;

		savingEntity = true;
		error = '';
		try {
			const parsedProperties = JSON.parse(editForm.properties);
			await apiFetch(`/knowledge/graph/entities/${selectedEntity.id}`, {
				method: 'PATCH',
				body: JSON.stringify({
					name: editForm.name,
					entity_type: editForm.type,
					properties: parsedProperties,
					confidence: editForm.confidence
				})
			});
			editingEntity = false;
			propertiesJsonError = '';
			closeDetail();
			await refreshGraph();
		} catch (e) {
			if (e instanceof SyntaxError) {
				propertiesJsonError = 'Invalid JSON';
			} else {
				error = e instanceof Error ? e.message : 'Failed to save entity';
			}
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
			await refreshGraph();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete entity';
		}
	}

</script>

<div class="flex h-full min-h-0 min-w-0 flex-col">
	<!-- Top toolbar -->
	<div class="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
		<!-- Toggle filter sidebar -->
		<button
			type="button"
			onclick={() => (showFilterPanel = !showFilterPanel)}
			class="inline-flex shrink-0 items-center rounded-md border border-border p-1.5 text-text-secondary transition-colors hover:bg-surface-hover"
			title="{showFilterPanel ? 'Hide' : 'Show'} filter panel"
		>
			{#if showFilterPanel}
				<PanelLeftClose size={14} />
			{:else}
				<PanelLeft size={14} />
			{/if}
		</button>

		<!-- Refresh -->
		<button
			type="button"
			onclick={() => refreshGraph()}
			class="inline-flex shrink-0 items-center rounded-md border border-border p-1.5 text-text-secondary transition-colors hover:bg-surface-hover"
			title="Refresh graph data"
		>
			<RefreshCw size={14} />
		</button>

		<!-- Spacer -->
		<div class="flex-1"></div>

		<!-- Regenerate status message -->
		{#if regenerateMessage}
			<span class="text-xs text-text-secondary">{regenerateMessage}</span>
		{/if}

		<!-- Regenerate KG button -->
		{#if onRegenerate}
			<button
				type="button"
				onclick={onRegenerate}
				disabled={regenerating}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
			>
				{#if regenerating}
					<Loader2 size={13} class="animate-spin" />
					Regenerating...
				{:else}
					<Sparkles size={13} />
					Regenerate
				{/if}
			</button>
		{/if}
	</div>

	<!-- Regeneration progress bar -->
	{#if regenerating}
		<div class="h-1 w-full shrink-0 overflow-hidden bg-surface-secondary">
			<div
				class="h-full rounded-full bg-accent transition-all duration-500"
				style="width: {regenerateProgress}%"
			></div>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="mb-2 flex shrink-0 items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
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
			<!-- ============================================================= -->
			<!-- Filter Sidebar                                                 -->
			<!-- ============================================================= -->
			{#if showFilterPanel}
				<div
					class="flex w-52 shrink-0 flex-col border-r border-border bg-surface-secondary/50"
					transition:slide={{ axis: 'x', duration: 200 }}
				>
					<!-- Sidebar header -->
					<div class="flex items-center justify-between border-b border-border px-3 py-2">
						<div class="flex items-center gap-1.5">
							<Filter size={12} class="text-text-secondary" />
							<span class="text-xs font-semibold text-text-secondary">Entity Types</span>
						</div>
						<span class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
							{visibleTypeCount}/{typeCounts.length}
						</span>
					</div>

					<!-- Quick actions -->
					<div class="flex gap-1 border-b border-border px-3 py-1.5">
						<button
							type="button"
							onclick={showAllTypes}
							class="rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors
								{hiddenTypes.size === 0 ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:bg-surface-hover'}"
						>
							Show All
						</button>
						<button
							type="button"
							onclick={hideAllTypes}
							class="rounded px-1.5 py-0.5 text-[10px] font-medium text-text-secondary transition-colors hover:bg-surface-hover"
						>
							Hide All
						</button>
					</div>

					<!-- Type search -->
					<div class="border-b border-border px-3 py-1.5">
						<input
							type="text"
							bind:value={filterSearch}
							placeholder="Filter types..."
							class="w-full rounded border border-border bg-surface px-2 py-1 text-[11px] text-text-primary outline-none focus:border-accent"
						/>
					</div>

					<!-- Type list -->
					<div class="flex-1 overflow-y-auto">
						{#each filteredTypeCounts as [type, count]}
							<button
								type="button"
								onclick={() => toggleTypeFilter(type)}
								ondblclick={() => showOnlyType(type)}
								class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-surface-hover
									{hiddenTypes.has(type) ? 'opacity-40' : ''}"
								title="Click to toggle, double-click to show only this type"
							>
								<span
									class="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
									style="background-color: {getTypeColor(type)}"
								></span>
								<span class="min-w-0 flex-1 truncate text-[11px] capitalize text-text-primary">
									{type.replace(/_/g, ' ')}
								</span>
								<span class="shrink-0 text-[10px] tabular-nums text-text-secondary">
									{count}
								</span>
							</button>
						{/each}
					</div>

					<!-- Stats footer -->
					{#if stats}
						<div class="border-t border-border px-3 py-2">
							<div class="flex justify-between text-[10px]">
								<span class="text-text-secondary">Entities</span>
								<span class="font-semibold text-text-primary">{stats.entity_count.toLocaleString()}</span>
							</div>
							<div class="flex justify-between text-[10px]">
								<span class="text-text-secondary">Relations</span>
								<span class="font-semibold text-text-primary">{stats.relation_count.toLocaleString()}</span>
							</div>
							<div class="flex justify-between text-[10px]">
								<span class="text-text-secondary">Showing</span>
								<span class="font-semibold text-text-primary">{filteredEntities.length.toLocaleString()}</span>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			<!-- ============================================================= -->
			<!-- Graph View                                                     -->
			<!-- ============================================================= -->
			<div
				class="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-surface"
				bind:this={containerEl}
			>
				{#if filteredEntities.length === 0}
					<div class="absolute inset-0 flex flex-col items-center justify-center text-text-secondary">
						<Network size={48} strokeWidth={1} class="mb-2 opacity-30" />
						<p class="text-sm">No entities match the current filters.</p>
						{#if hiddenTypes.size > 0}
							<button
								type="button"
								onclick={showAllTypes}
								class="mt-2 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90"
							>
								Show All Types
							</button>
						{/if}
					</div>
				{:else}
					<div bind:this={graphContainerEl} class="h-full w-full"></div>
				{/if}

				<!-- Camera controls — fit-to-view for 3D -->
				<div class="absolute bottom-3 right-3 flex flex-col gap-1">
					<button
						type="button"
						onclick={() => { if (graphInstance) graphInstance.zoomToFit(500, 50); }}
						class="rounded-md border border-border bg-surface/90 p-1.5 text-text-secondary shadow-sm backdrop-blur-sm transition-colors hover:bg-surface-hover"
						title="Fit to View"
					>
						<Maximize2 size={14} />
					</button>
				</div>
			</div>

			<!-- ============================================================= -->
			<!-- Detail / Edit Slide-Out Panel                                 -->
			<!-- ============================================================= -->
			{#if selectedEntity}
				<div
					class="absolute inset-y-0 right-0 z-10 flex w-72 shrink-0 flex-col border-l border-border bg-surface shadow-lg"
					transition:fly={{ x: 288, duration: 200 }}
				>
					<!-- Panel header -->
					<div class="flex items-center justify-between border-b border-border px-3 py-2">
						<div class="flex items-center gap-1.5">
							<h4 class="text-xs font-semibold text-text-primary">
								{editingEntity ? 'Edit Entity' : 'Entity Detail'}
							</h4>
							{#if editingEntity && editFormModified}
								<span class="inline-flex items-center gap-0.5 rounded-full bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-warning">
									<Pencil size={8} />
									modified
								</span>
							{:else if !editingEntity}
								<span class="inline-flex items-center gap-0.5 rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
									<Check size={8} />
									verified
								</span>
							{/if}
						</div>
						<div class="flex items-center gap-0.5">
							{#if !editingEntity}
								<button
									type="button"
									onclick={startEditEntity}
									class="rounded p-1 text-text-secondary hover:bg-accent/10 hover:text-accent"
									title="Edit"
								>
									<Pencil size={11} />
								</button>
								<button
									type="button"
									onclick={() => deleteEntity(selectedEntity!.id)}
									class="rounded p-1 text-text-secondary hover:bg-danger/10 hover:text-danger"
									title="Delete"
								>
									<Trash2 size={11} />
								</button>
							{/if}
							<button
								type="button"
								onclick={editingEntity ? cancelEdit : closeDetail}
								class="rounded p-1 text-text-secondary hover:text-text-primary"
								title="Close"
							>
								<X size={13} />
							</button>
						</div>
					</div>

					<!-- Panel body -->
					<div class="flex-1 overflow-y-auto p-3">
						{#if loadingDetail}
							<div class="flex items-center justify-center py-8">
								<Loader2 size={14} class="animate-spin text-text-secondary" />
							</div>
						{:else if editingEntity}
							<!-- Edit Mode -->
							<div class="flex flex-col gap-2.5">
								<div>
									<label for="edit-name" class="mb-0.5 block text-[10px] font-medium text-text-secondary">Name</label>
									<input id="edit-name" type="text" bind:value={editForm.name} class="w-full rounded border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none focus:border-accent" />
								</div>
								<div>
									<label for="edit-type" class="mb-0.5 block text-[10px] font-medium text-text-secondary">Type</label>
									<input id="edit-type" type="text" bind:value={editForm.type} class="w-full rounded border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none focus:border-accent" />
								</div>
								<div>
									<label for="edit-confidence" class="mb-0.5 flex justify-between text-[10px] font-medium text-text-secondary">
										<span>Confidence</span>
										<span class="tabular-nums">{editForm.confidence.toFixed(2)}</span>
									</label>
									<input id="edit-confidence" type="range" min="0" max="1" step="0.01" bind:value={editForm.confidence} class="w-full accent-accent" />
								</div>
								<div>
									<label for="edit-properties" class="mb-0.5 block text-[10px] font-medium text-text-secondary">Properties (JSON)</label>
									<textarea
										id="edit-properties"
										bind:value={editForm.properties}
										oninput={() => validatePropertiesJson(editForm.properties)}
										rows={5}
										class="w-full resize-y rounded border bg-surface px-2 py-1 font-mono text-[10px] text-text-primary outline-none
											{propertiesJsonError ? 'border-danger' : 'border-border focus:border-accent'}"
										spellcheck="false"
									></textarea>
									{#if propertiesJsonError}
										<p class="mt-0.5 text-[10px] text-danger">{propertiesJsonError}</p>
									{/if}
								</div>
							</div>
						{:else}
							<!-- View Mode -->
							<div class="flex flex-col gap-2.5">
								<div>
									<h5 class="text-xs font-semibold text-text-primary">{selectedEntity.name}</h5>
									<span
										class="mt-0.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium capitalize"
										style="background-color: {getTypeColor(selectedEntity.type)}20; color: {getTypeColor(selectedEntity.type)}"
									>
										<span class="inline-block h-1.5 w-1.5 rounded-full" style="background-color: {getTypeColor(selectedEntity.type)}"></span>
										{selectedEntity.type}
									</span>
								</div>

								{#if selectedEntity.confidence != null}
									<div>
										<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Confidence</h6>
										<div class="flex items-center gap-2">
											<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-secondary">
												<div class="h-full rounded-full bg-accent" style="width: {(selectedEntity.confidence ?? 1) * 100}%"></div>
											</div>
											<span class="text-[10px] tabular-nums text-text-secondary">{Math.round((selectedEntity.confidence ?? 1) * 100)}%</span>
										</div>
									</div>
								{/if}

								{#if selectedEntity.properties && Object.keys(selectedEntity.properties).length > 0}
									<div>
										<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Properties</h6>
										<div class="rounded border border-border bg-surface-secondary p-1.5">
											{#each Object.entries(selectedEntity.properties) as [key, value]}
												<div class="flex items-start gap-1.5 py-0.5 text-[10px]">
													<span class="font-medium text-text-secondary">{key}:</span>
													<span class="text-text-primary">{String(value)}</span>
												</div>
											{/each}
										</div>
									</div>
								{/if}

								{#if neighborhood?.entities}
									{@const neighbors = neighborhood.entities.filter((e) => e.id !== selectedEntity?.id)}
									{#if neighbors.length > 0}
										<div>
											<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Related Entities ({neighbors.length})</h6>
											<div class="flex flex-col gap-0.5">
												{#each neighbors.slice(0, 15) as neighbor}
													<button
														type="button"
														onclick={() => selectEntity(neighbor)}
														class="flex items-center gap-1.5 rounded px-1.5 py-1 text-left text-[10px] transition-colors hover:bg-surface-secondary"
													>
														<span class="inline-block h-2 w-2 rounded-full" style="background-color: {getTypeColor(neighbor.type ?? '')}"></span>
														<span class="min-w-0 flex-1 truncate font-medium text-text-primary">{neighbor.name ?? 'Unnamed'}</span>
														<span class="shrink-0 capitalize text-text-secondary">{neighbor.type ?? 'unknown'}</span>
													</button>
												{/each}
												{#if neighbors.length > 15}
													<span class="px-1.5 text-[10px] text-text-secondary">+{neighbors.length - 15} more</span>
												{/if}
											</div>
										</div>
									{/if}
								{/if}

								{#if neighborhood?.relations && neighborhood.relations.length > 0}
									<div>
										<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Relations ({neighborhood.relations.length})</h6>
										<div class="flex flex-col gap-0.5">
											{#each neighborhood.relations.slice(0, 15) as rel}
												<div class="rounded border border-border bg-surface-secondary px-1.5 py-1 text-[10px]">
													<span class="font-medium text-accent">{rel.label}</span>
												</div>
											{/each}
											{#if neighborhood.relations.length > 15}
												<span class="px-1.5 text-[10px] text-text-secondary">+{neighborhood.relations.length - 15} more</span>
											{/if}
										</div>
									</div>
								{/if}

								{#if selectedEntity.source_documents && selectedEntity.source_documents.length > 0}
									<div>
										<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Source Documents ({selectedEntity.source_documents.length})</h6>
										<div class="flex flex-col gap-0.5">
											{#each selectedEntity.source_documents.slice(0, 5) as docId}
												<div class="rounded bg-surface-secondary px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">{docId}</div>
											{/each}
										</div>
									</div>
								{/if}
							</div>
						{/if}
					</div>

					<!-- Panel footer: Save / Cancel (edit mode only) -->
					{#if editingEntity}
						<div class="flex items-center gap-2 border-t border-border px-3 py-2">
							<button
								type="button"
								onclick={saveEntity}
								disabled={savingEntity || !!propertiesJsonError}
								class="inline-flex flex-1 items-center justify-center gap-1 rounded-md bg-accent px-2.5 py-1.5 text-[10px] font-medium text-white hover:bg-accent/90 disabled:opacity-50"
							>
								{#if savingEntity}
									<Loader2 size={10} class="animate-spin" />
									Saving...
								{:else}
									<Save size={10} />
									Save
								{/if}
							</button>
							<button
								type="button"
								onclick={cancelEdit}
								class="inline-flex flex-1 items-center justify-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-[10px] font-medium text-text-secondary hover:bg-surface-hover"
							>
								Cancel
							</button>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>
