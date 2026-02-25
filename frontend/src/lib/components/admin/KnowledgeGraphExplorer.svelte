<!--
  KnowledgeGraphExplorer.svelte - Knowledge graph visualization and management.

  D3 force-directed graph designed for large graphs (hundreds of nodes).
  Features: collapsible filter sidebar with type counts, zoom/pan,
  node search, grouped list view, entity detail/edit slide-out panel,
  stats overlay, and CRUD operations. All panels contained within the
  parent flex container — no width overflow.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import { fly, slide } from 'svelte/transition';
	import * as d3 from 'd3';
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
		Filter,
		Save,
		Check,
		RefreshCw,
		ZoomIn,
		ZoomOut,
		Maximize2,
		PanelLeftClose,
		PanelLeft
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import type { GraphEntity, GraphRelation } from '$lib/components/flow/flow-types.js';

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

	interface SimNode extends d3.SimulationNodeDatum {
		id: string;
		name: string;
		type: string;
		entity: GraphEntity;
	}

	interface SimLink extends d3.SimulationLinkDatum<SimNode> {
		id: string;
		label: string;
		relation: GraphRelation;
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

	// List view state
	let expandedTypes = $state<Set<string>>(new Set());

	// D3 refs
	let svgEl: SVGSVGElement;
	let containerEl: HTMLDivElement;
	let simulation: d3.Simulation<SimNode, SimLink> | null = null;
	let currentZoom: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;

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

	const NODE_RADIUS = 5;

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
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(
				(e) =>
					(e.name ?? '').toLowerCase().includes(q) ||
					(e.type ?? '').toLowerCase().includes(q)
			);
		}
		if (hiddenTypes.size > 0) {
			result = result.filter((e) => !hiddenTypes.has((e.type ?? '').toLowerCase()));
		}
		return result;
	});

	let entitiesByType = $derived.by(() => {
		const groups: Record<string, GraphEntity[]> = {};
		for (const entity of filteredEntities) {
			const type = (entity.type ?? 'unknown').toLowerCase();
			if (!groups[type]) groups[type] = [];
			groups[type].push(entity);
		}
		return groups;
	});

	/** Number of visible types (not hidden). */
	let visibleTypeCount = $derived(typeCounts.length - hiddenTypes.size);

	// -----------------------------------------------------------------------
	// D3 Force Graph
	// -----------------------------------------------------------------------

	function buildGraph() {
		if (!svgEl || !containerEl) return;

		// Clear previous
		d3.select(svgEl).selectAll('*').remove();
		if (simulation) {
			simulation.stop();
			simulation = null;
		}

		if (filteredEntities.length === 0) return;

		const rect = containerEl.getBoundingClientRect();
		const width = rect.width;
		const height = rect.height;
		if (width === 0 || height === 0) return;

		const filteredIds = new Set(filteredEntities.map((e) => e.id));

		const nodes: SimNode[] = filteredEntities.map((e) => ({
			id: e.id,
			name: e.name ?? 'Unnamed',
			type: (e.type ?? 'unknown').toLowerCase(),
			entity: e
		}));

		const visibleRelations = relations.filter(
			(r) => filteredIds.has(r.source_id) && filteredIds.has(r.target_id)
		);

		const nodeMap = new Map(nodes.map((n) => [n.id, n]));
		const links: SimLink[] = visibleRelations
			.filter((r) => nodeMap.has(r.source_id) && nodeMap.has(r.target_id))
			.map((r) => ({
				id: r.id,
				source: nodeMap.get(r.source_id)!,
				target: nodeMap.get(r.target_id)!,
				label: r.label || r.relation_type,
				relation: r
			}));

		const svg = d3
			.select(svgEl)
			.attr('width', width)
			.attr('height', height)
			.attr('viewBox', `0 0 ${width} ${height}`);

		// Arrow marker
		const defs = svg.append('defs');
		defs
			.append('marker')
			.attr('id', 'arrowhead')
			.attr('viewBox', '0 -4 8 8')
			.attr('refX', NODE_RADIUS + 10)
			.attr('refY', 0)
			.attr('markerWidth', 5)
			.attr('markerHeight', 5)
			.attr('orient', 'auto')
			.append('path')
			.attr('d', 'M0,-3L7,0L0,3')
			.attr('fill', 'var(--color-text-secondary)')
			.attr('opacity', 0.35);

		const g = svg.append('g');

		const zoom = d3
			.zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.02, 10])
			.on('zoom', (event) => {
				g.attr('transform', event.transform);
			});

		svg.call(zoom);
		currentZoom = zoom;

		// Links
		const link = g
			.append('g')
			.attr('class', 'links')
			.selectAll('line')
			.data(links)
			.join('line')
			.attr('stroke', 'var(--color-border)')
			.attr('stroke-width', 0.5)
			.attr('stroke-opacity', 0.35)
			.attr('marker-end', 'url(#arrowhead)');

		// Edge labels (visible at high zoom)
		const edgeLabel = g
			.append('g')
			.attr('class', 'edge-labels')
			.selectAll('text')
			.data(links)
			.join('text')
			.text((d) => d.label)
			.attr('font-size', 7)
			.attr('fill', 'var(--color-text-secondary)')
			.attr('text-anchor', 'middle')
			.attr('dy', -3)
			.attr('opacity', 0);

		// Nodes
		const node = g
			.append('g')
			.attr('class', 'nodes')
			.selectAll<SVGCircleElement, SimNode>('circle')
			.data(nodes)
			.join('circle')
			.attr('r', NODE_RADIUS)
			.attr('fill', (d) => getTypeColor(d.type))
			.attr('stroke', 'var(--color-surface)')
			.attr('stroke-width', 1)
			.attr('cursor', 'pointer')
			.on('mouseover', function (event, d) {
				d3.select(this).transition().duration(100).attr('r', NODE_RADIUS * 1.8).attr('stroke-width', 2);
				tooltip
					.style('opacity', 1)
					.html(
						`<strong>${d.name}</strong><br/><span style="color:${getTypeColor(d.type)}">${d.type}</span>`
					)
					.style('left', event.pageX + 12 + 'px')
					.style('top', event.pageY - 10 + 'px');
			})
			.on('mouseout', function () {
				d3.select(this).transition().duration(100).attr('r', NODE_RADIUS).attr('stroke-width', 1);
				tooltip.style('opacity', 0);
			})
			.on('click', (_event, d) => {
				selectEntity(d.entity);
				highlightNode(d.id);
			})
			.call(
				d3
					.drag<SVGCircleElement, SimNode>()
					.on('start', (event, d) => {
						if (!event.active) simulation!.alphaTarget(0.3).restart();
						d.fx = d.x;
						d.fy = d.y;
					})
					.on('drag', (event, d) => {
						d.fx = event.x;
						d.fy = event.y;
					})
					.on('end', (event, d) => {
						if (!event.active) simulation!.alphaTarget(0);
						d.fx = null;
						d.fy = null;
					})
			);

		// Node labels (visible at medium+ zoom)
		const label = g
			.append('g')
			.attr('class', 'labels')
			.selectAll('text')
			.data(nodes)
			.join('text')
			.text((d) => d.name.length > 20 ? d.name.slice(0, 18) + '…' : d.name)
			.attr('font-size', 8)
			.attr('fill', 'var(--color-text-primary)')
			.attr('dx', NODE_RADIUS + 3)
			.attr('dy', 3)
			.attr('pointer-events', 'none')
			.attr('opacity', 0);

		// Tooltip
		const tooltip = d3
			.select(containerEl)
			.selectAll<HTMLDivElement, unknown>('.kg-tooltip')
			.data([0])
			.join('div')
			.attr('class', 'kg-tooltip')
			.style('position', 'fixed')
			.style('pointer-events', 'none')
			.style('padding', '6px 10px')
			.style('background', 'var(--color-surface)')
			.style('border', '1px solid var(--color-border)')
			.style('border-radius', '6px')
			.style('font-size', '11px')
			.style('color', 'var(--color-text-primary)')
			.style('box-shadow', '0 4px 12px rgba(0,0,0,0.15)')
			.style('z-index', '50')
			.style('opacity', '0')
			.style('transition', 'opacity 0.15s');

		// Force simulation — tuned for large graphs
		const n = nodes.length;
		const chargeStrength = n > 300 ? -50 : n > 150 ? -80 : n > 50 ? -120 : -200;
		const linkDistance = n > 300 ? 30 : n > 150 ? 45 : n > 50 ? 60 : 80;

		simulation = d3
			.forceSimulation<SimNode>(nodes)
			.force(
				'link',
				d3
					.forceLink<SimNode, SimLink>(links)
					.id((d) => d.id)
					.distance(linkDistance)
			)
			.force('charge', d3.forceManyBody().strength(chargeStrength))
			.force('center', d3.forceCenter(width / 2, height / 2))
			.force('collision', d3.forceCollide(NODE_RADIUS + 2))
			.force('x', d3.forceX(width / 2).strength(0.04))
			.force('y', d3.forceY(height / 2).strength(0.04))
			.on('tick', () => {
				link
					.attr('x1', (d) => (d.source as SimNode).x!)
					.attr('y1', (d) => (d.source as SimNode).y!)
					.attr('x2', (d) => (d.target as SimNode).x!)
					.attr('y2', (d) => (d.target as SimNode).y!);

				edgeLabel
					.attr('x', (d) => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
					.attr('y', (d) => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2);

				node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
				label.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
			});

		// Adaptive rendering based on zoom
		zoom.on('zoom.adaptive', (event) => {
			const k = event.transform.k;
			// Show labels when zoomed in enough to read them
			label.attr('opacity', k > 0.8 ? Math.min(1, (k - 0.8) * 2) : 0);
			// Show edge labels only when very zoomed in
			edgeLabel.attr('opacity', k > 2 ? 0.7 : 0);
		});

		// Fit after simulation settles
		setTimeout(() => fitToView(), 1000);
	}

	function fitToView() {
		if (!svgEl || !currentZoom || !containerEl) return;
		const svg = d3.select(svgEl);
		const g = svg.select<SVGGElement>('g');
		const gNode = g.node();
		if (!gNode) return;
		const bounds = gNode.getBBox();
		if (bounds.width === 0 || bounds.height === 0) return;

		const rect = containerEl.getBoundingClientRect();
		const padding = 40;
		const scale = Math.min(
			(rect.width - padding * 2) / bounds.width,
			(rect.height - padding * 2) / bounds.height,
			2
		);
		const tx = rect.width / 2 - scale * (bounds.x + bounds.width / 2);
		const ty = rect.height / 2 - scale * (bounds.y + bounds.height / 2);
		(svg as any)
			.transition()
			.duration(500)
			.call(currentZoom!.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
	}

	function highlightNode(nodeId: string) {
		if (!svgEl) return;
		const svg = d3.select(svgEl);

		const neighborIds = new Set<string>([nodeId]);
		for (const r of relations) {
			if (r.source_id === nodeId) neighborIds.add(r.target_id);
			if (r.target_id === nodeId) neighborIds.add(r.source_id);
		}

		svg.selectAll<SVGCircleElement, SimNode>('.nodes circle')
			.attr('opacity', (d) => neighborIds.has(d.id) ? 1 : 0.15)
			.attr('stroke-width', (d) => d.id === nodeId ? 3 : 1);

		svg.selectAll<SVGLineElement, SimLink>('.links line')
			.attr('stroke-opacity', (d) =>
				(d.source as SimNode).id === nodeId || (d.target as SimNode).id === nodeId ? 0.8 : 0.03
			)
			.attr('stroke-width', (d) =>
				(d.source as SimNode).id === nodeId || (d.target as SimNode).id === nodeId ? 1.5 : 0.5
			);

		svg.selectAll<SVGTextElement, SimNode>('.labels text')
			.attr('opacity', (d) => neighborIds.has(d.id) ? 1 : 0);
	}

	function clearHighlight() {
		if (!svgEl) return;
		const svg = d3.select(svgEl);
		svg.selectAll('.nodes circle').attr('opacity', 1).attr('stroke-width', 1);
		svg.selectAll('.links line').attr('stroke-opacity', 0.35).attr('stroke-width', 0.5);
		// Labels controlled by zoom level, just reset to hidden for now
		svg.selectAll('.labels text').attr('opacity', 0);
	}

	function handleZoomIn() {
		if (!svgEl || !currentZoom) return;
		d3.select(svgEl).transition().duration(300).call(currentZoom.scaleBy, 1.5);
	}

	function handleZoomOut() {
		if (!svgEl || !currentZoom) return;
		d3.select(svgEl).transition().duration(300).call(currentZoom.scaleBy, 0.67);
	}

	// Rebuild graph when data changes
	let graphVersion = $state(0);
	$effect(() => {
		void filteredEntities;
		void relations;
		void viewMode;
		void graphVersion;

		if (viewMode === 'graph' && !loading && filteredEntities.length > 0) {
			tick().then(() => buildGraph());
		}
	});

	// Resize handler
	$effect(() => {
		if (!containerEl) return;
		let debounce: ReturnType<typeof setTimeout>;
		const observer = new ResizeObserver(() => {
			clearTimeout(debounce);
			debounce = setTimeout(() => {
				if (viewMode === 'graph' && filteredEntities.length > 0) {
					buildGraph();
				}
			}, 200);
		});
		observer.observe(containerEl);
		return () => {
			observer.disconnect();
			clearTimeout(debounce);
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

	function toggleTypeGroup(type: string) {
		const next = new Set(expandedTypes);
		if (next.has(type)) next.delete(type);
		else next.add(type);
		expandedTypes = next;
	}
</script>

<div class="flex h-full min-h-0 min-w-0 flex-col">
	<!-- Top toolbar -->
	<div class="flex shrink-0 items-center gap-2 px-1 pb-2">
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

		<!-- Search -->
		<div class="relative min-w-0 flex-1">
			<Search size={14} class="absolute top-1/2 left-2.5 -translate-y-1/2 text-text-secondary" />
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search entities by name or type..."
				class="w-full rounded-md border border-border bg-surface py-1.5 pr-3 pl-8 text-xs text-text-primary outline-none focus:border-accent"
			/>
		</div>

		<!-- Refresh -->
		<button
			type="button"
			onclick={() => refreshGraph()}
			class="inline-flex shrink-0 items-center rounded-md border border-border p-1.5 text-text-secondary transition-colors hover:bg-surface-hover"
			title="Refresh"
		>
			<RefreshCw size={14} />
		</button>

		<!-- View toggle -->
		<div class="flex shrink-0 rounded-md border border-border">
			<button
				type="button"
				onclick={() => (viewMode = 'graph')}
				class="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium transition-colors
					{viewMode === 'graph' ? 'bg-accent text-white' : 'text-text-secondary hover:bg-surface-hover'}"
			>
				<Network size={13} />
				Graph
			</button>
			<button
				type="button"
				onclick={() => (viewMode = 'list')}
				class="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium transition-colors
					{viewMode === 'list' ? 'bg-accent text-white' : 'text-text-secondary hover:bg-surface-hover'}"
			>
				<List size={13} />
				List
			</button>
		</div>
	</div>

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
			{#if viewMode === 'graph'}
				<div
					class="relative min-h-0 min-w-0 flex-1 bg-surface"
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
						<svg bind:this={svgEl} class="h-full w-full"></svg>
					{/if}

					<!-- Zoom controls -->
					<div class="absolute bottom-3 right-3 flex flex-col gap-1">
						<button
							type="button"
							onclick={handleZoomIn}
							class="rounded-md border border-border bg-surface/90 p-1.5 text-text-secondary shadow-sm backdrop-blur-sm transition-colors hover:bg-surface-hover"
							title="Zoom In"
						>
							<ZoomIn size={14} />
						</button>
						<button
							type="button"
							onclick={handleZoomOut}
							class="rounded-md border border-border bg-surface/90 p-1.5 text-text-secondary shadow-sm backdrop-blur-sm transition-colors hover:bg-surface-hover"
							title="Zoom Out"
						>
							<ZoomOut size={14} />
						</button>
						<button
							type="button"
							onclick={() => fitToView()}
							class="rounded-md border border-border bg-surface/90 p-1.5 text-text-secondary shadow-sm backdrop-blur-sm transition-colors hover:bg-surface-hover"
							title="Fit to View"
						>
							<Maximize2 size={14} />
						</button>
					</div>
				</div>

			<!-- ============================================================= -->
			<!-- List View                                                      -->
			<!-- ============================================================= -->
			{:else}
				<div class="min-w-0 flex-1 overflow-y-auto bg-surface p-3">
					{#if Object.keys(entitiesByType).length === 0}
						<div class="flex flex-col items-center justify-center py-12 text-text-secondary">
							<Network size={48} strokeWidth={1} class="mb-2 opacity-30" />
							<p class="text-sm">No entities found.</p>
						</div>
					{:else}
						<div class="flex flex-col gap-1.5">
							{#each Object.entries(entitiesByType).sort((a, b) => b[1].length - a[1].length) as [type, typeEntities]}
								<div class="rounded-lg border border-border bg-surface">
									<button
										type="button"
										onclick={() => toggleTypeGroup(type)}
										class="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-surface-secondary/50"
									>
										{#if expandedTypes.has(type)}
											<ChevronDown size={13} class="text-text-secondary" />
										{:else}
											<ChevronRight size={13} class="text-text-secondary" />
										{/if}
										<span
											class="inline-block h-2.5 w-2.5 rounded-full"
											style="background-color: {getTypeColor(type)}"
										></span>
										<span class="text-xs font-medium capitalize text-text-primary">
											{type.replace(/_/g, ' ')}
										</span>
										<span class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
											{typeEntities.length}
										</span>
									</button>

									{#if expandedTypes.has(type)}
										<div class="border-t border-border px-3 py-1.5" transition:slide={{ duration: 150 }}>
											<div class="flex flex-col gap-1">
												{#each typeEntities as entity}
													<button
														type="button"
														onclick={() => selectEntity(entity)}
														class="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left transition-colors hover:bg-surface-secondary/50
															{selectedEntity?.id === entity.id ? 'bg-accent/5 ring-1 ring-accent/30' : ''}"
													>
														<span class="min-w-0 flex-1 truncate text-xs font-medium text-text-primary">
															{entity.name}
														</span>
														{#if entity.confidence != null && entity.confidence < 1.0}
															<span class="shrink-0 rounded bg-warning/10 px-1 py-0.5 text-[10px] text-warning">
																{Math.round(entity.confidence * 100)}%
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
