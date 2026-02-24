<!--
  KnowledgeBaseManager.svelte - Knowledge base document management.

  Main admin panel for the knowledge base with three tabs:
  Documents (filterable table), Add Document (multi-method ingestion),
  and Graph Explorer (D3 force graph + list view). Includes a statistics
  sidebar with counts by type, total chunks, and total entities.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Trash2,
		Loader2,
		FileText,
		BarChart3,
		BookOpen,
		Plus,
		Network,
		Hash,
		Layers,
		Archive,
		RefreshCw
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import { parseSSEStream } from '$lib/services/sse.js';
	import KnowledgeAddDocument from './KnowledgeAddDocument.svelte';
	import KnowledgeDocumentDetail from './KnowledgeDocumentDetail.svelte';
	import KnowledgeGraphExplorer from './KnowledgeGraphExplorer.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface KnowledgeDocument {
		id: string;
		title: string;
		type: string;
		source: string;
		tags: string[];
		status?: string;
		chunk_count?: number;
		created_at?: string;
	}

	interface GraphStats {
		total_entities: number;
		total_relations: number;
		entities_by_type: Record<string, number>;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let activeTab = $state<'documents' | 'add' | 'graph'>('documents');
	let documents = $state<KnowledgeDocument[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let showStats = $state(true);
	let statusFilter = $state('all');

	// Selection
	let selectedDocumentId = $state<string | null>(null);
	let selectedIds = $state<Set<string>>(new Set());

	// Statistics
	let stats = $state<GraphStats | null>(null);
	let loadingStats = $state(true);

	// KG recompute
	let recomputingKG = $state(false);
	let kgRecomputeMessage = $state('');
	let kgRecomputeProgress = $state(0);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let filteredDocuments = $derived.by(() => {
		return documents.filter((d) => {
			const matchesSearch =
				!searchQuery.trim() ||
				d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
				d.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
				d.source.toLowerCase().includes(searchQuery.toLowerCase()) ||
				d.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
			const matchesStatus = statusFilter === 'all' || d.status === statusFilter;
			return matchesSearch && matchesStatus;
		});
	});

	let docCountsByType = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const doc of documents) {
			const type = doc.type || 'unknown';
			counts[type] = (counts[type] || 0) + 1;
		}
		return counts;
	});

	let totalChunks = $derived(
		documents.reduce((sum, d) => sum + (d.chunk_count ?? 0), 0)
	);

	let allSelected = $derived(
		filteredDocuments.length > 0 && filteredDocuments.every((d) => selectedIds.has(d.id))
	);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadDocuments() {
		loading = true;
		error = '';
		try {
			documents = await apiJson<KnowledgeDocument[]>('/knowledge/documents');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load documents';
		} finally {
			loading = false;
		}
	}

	async function loadStats() {
		loadingStats = true;
		try {
			stats = await apiJson<GraphStats>('/knowledge/graph/stats');
		} catch {
			// Stats are optional -- component works without them
			stats = null;
		} finally {
			loadingStats = false;
		}
	}

	async function triggerKGRecompute() {
		recomputingKG = true;
		kgRecomputeProgress = 0;
		kgRecomputeMessage = 'Submitting KG recompute job...';
		error = '';
		try {
			const resp = await apiJson<{ job_id: string; status: string }>(
				'/knowledge/graph/recompute',
				{ method: 'POST' }
			);
			kgRecomputeMessage = 'Recomputing knowledge graph...';
			const response = await apiFetch(`/jobs/${resp.job_id}/stream`);
			await parseSSEStream(
				response,
				(msg) => {
					if (msg.event === 'job_progress') {
						kgRecomputeProgress =
							(msg.data.progress_pct as number) ?? kgRecomputeProgress;
						if (msg.data.progress_message)
							kgRecomputeMessage = msg.data.progress_message as string;
					} else if (msg.event === 'done') {
						if (msg.data.error) error = `KG recompute failed: ${msg.data.error}`;
					}
				},
				(err) => {
					error = `Stream error: ${err.message}`;
				},
				async () => {
					recomputingKG = false;
					kgRecomputeMessage = '';
					kgRecomputeProgress = 0;
					await loadStats();
				}
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to trigger KG recompute';
			recomputingKG = false;
			kgRecomputeMessage = '';
		}
	}

	$effect(() => {
		loadDocuments();
		loadStats();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	async function deleteDocument(id: string) {
		error = '';
		try {
			await apiFetch(`/knowledge/documents/${id}`, { method: 'DELETE' });
			selectedIds.delete(id);
			selectedIds = new Set(selectedIds);
			if (selectedDocumentId === id) {
				selectedDocumentId = null;
			}
			await loadDocuments();
			await loadStats();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete document';
		}
	}

	async function bulkDelete() {
		if (selectedIds.size === 0) return;
		if (!confirm(`Delete ${selectedIds.size} document(s)? This cannot be undone.`)) return;
		error = '';
		try {
			await apiJson('/knowledge/documents/bulk-delete', {
				method: 'POST',
				body: JSON.stringify({ document_ids: [...selectedIds] })
			});
			selectedIds = new Set();
			selectedDocumentId = null;
			await loadDocuments();
			await loadStats();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete documents';
		}
	}

	async function bulkArchive() {
		if (selectedIds.size === 0) return;
		error = '';
		try {
			await apiJson('/knowledge/documents/bulk-archive', {
				method: 'POST',
				body: JSON.stringify({ document_ids: [...selectedIds] })
			});
			selectedIds = new Set();
			await loadDocuments();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to archive documents';
		}
	}

	async function bulkReindex() {
		if (selectedIds.size === 0) return;
		error = '';
		try {
			await apiJson('/knowledge/documents/bulk-reindex', {
				method: 'POST',
				body: JSON.stringify({ document_ids: [...selectedIds] })
			});
			selectedIds = new Set();
			await loadDocuments();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to re-index documents';
		}
	}

	function toggleSelectAll() {
		if (allSelected) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(filteredDocuments.map((d) => d.id));
		}
	}

	function toggleSelect(id: string) {
		const next = new Set(selectedIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		selectedIds = next;
	}

	function handleDocumentAdded() {
		loadDocuments();
		loadStats();
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function statusBadge(status: string): { color: string; label: string } {
		switch (status) {
			case 'published':
				return { color: 'bg-success/10 text-success', label: 'Published' };
			case 'indexing':
				return { color: 'bg-accent/10 text-accent', label: 'Indexing' };
			case 'draft':
				return { color: 'bg-text-secondary/10 text-text-secondary', label: 'Draft' };
			case 'error':
				return { color: 'bg-danger/10 text-danger', label: 'Error' };
			case 'archived':
				return { color: 'bg-warning/10 text-warning', label: 'Archived' };
			default:
				return { color: 'bg-text-secondary/10 text-text-secondary', label: status || 'Unknown' };
		}
	}

	const typeBadgeColors: Record<string, string> = {
		text: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
		markdown: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
		html: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
		pdf: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
		code: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
		api_spec: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300',
		other: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
	};

	function formatDate(dateStr?: string): string {
		if (!dateStr) return '--';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<div class="flex h-full">
	<!-- Main content -->
	<div class="flex flex-1 flex-col gap-4 overflow-hidden p-6">
		<!-- Header -->
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Knowledge Base</h1>
				<p class="text-sm text-text-secondary">
					Manage documents, explore the knowledge graph, and add new content
				</p>
			</div>
			<button
				type="button"
				onclick={() => (showStats = !showStats)}
				class="rounded-md border border-border p-1.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				title="{showStats ? 'Hide' : 'Show'} statistics"
			>
				<BarChart3 size={16} />
			</button>
		</div>

		<!-- Error banner -->
		{#if error}
			<div
				class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
			>
				{error}
			</div>
		{/if}

		<!-- Tab bar -->
		<div class="flex gap-1 border-b border-border">
			<button
				type="button"
				onclick={() => (activeTab = 'documents')}
				class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
					{activeTab === 'documents'
					? 'border-b-2 border-accent text-accent'
					: 'text-text-secondary hover:text-text-primary'}"
			>
				<BookOpen size={14} />
				Documents
				{#if documents.length > 0}
					<span
						class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
					>
						{documents.length}
					</span>
				{/if}
			</button>
			<button
				type="button"
				onclick={() => (activeTab = 'add')}
				class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
					{activeTab === 'add'
					? 'border-b-2 border-accent text-accent'
					: 'text-text-secondary hover:text-text-primary'}"
			>
				<Plus size={14} />
				Add Document
			</button>
			<button
				type="button"
				onclick={() => (activeTab = 'graph')}
				class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
					{activeTab === 'graph'
					? 'border-b-2 border-accent text-accent'
					: 'text-text-secondary hover:text-text-primary'}"
			>
				<Network size={14} />
				Graph Explorer
			</button>
		</div>

		<!-- ================================================================= -->
		<!-- Documents Tab                                                      -->
		<!-- ================================================================= -->
		{#if activeTab === 'documents'}
			<div class="flex flex-1 flex-col gap-3 overflow-hidden">
				<!-- Search and bulk actions -->
				<div class="flex items-center gap-3">
					<div class="relative flex-1">
						<Search
							size={14}
							class="absolute top-1/2 left-3 -translate-y-1/2 text-text-secondary"
						/>
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="Search documents by title, type, source, or tags..."
							class="w-full rounded-md border border-border bg-surface py-1.5 pr-3 pl-8 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</div>

					<!-- Status filter dropdown -->
					<select
						bind:value={statusFilter}
						class="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						<option value="all">All statuses</option>
						<option value="published">Published</option>
						<option value="draft">Draft</option>
						<option value="indexing">Indexing</option>
						<option value="error">Error</option>
						<option value="archived">Archived</option>
					</select>

					{#if selectedIds.size > 0}
						<div class="flex items-center gap-1.5">
							<button
								type="button"
								onclick={bulkReindex}
								class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover"
							>
								<RefreshCw size={14} />
								Re-index ({selectedIds.size})
							</button>
							<button
								type="button"
								onclick={bulkArchive}
								class="inline-flex items-center gap-1.5 rounded-md border border-warning/50 px-3 py-1.5 text-sm font-medium text-warning transition-colors hover:bg-warning/10"
							>
								<Archive size={14} />
								Archive ({selectedIds.size})
							</button>
							<button
								type="button"
								onclick={bulkDelete}
								class="inline-flex items-center gap-1.5 rounded-md bg-danger px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-danger/90"
							>
								<Trash2 size={14} />
								Delete ({selectedIds.size})
							</button>
						</div>
					{/if}
				</div>

				<!-- Document detail panel or table -->
				{#if selectedDocumentId}
					<div class="flex flex-1 gap-3 overflow-hidden">
						<!-- Table (narrower) -->
						<div class="flex-1 overflow-auto rounded-lg border border-border bg-surface">
							{@render documentTable()}
						</div>

						<!-- Detail panel -->
						<div class="w-96 shrink-0">
							<KnowledgeDocumentDetail
								documentId={selectedDocumentId}
								onClose={() => (selectedDocumentId = null)}
								onDeleted={() => {
									selectedDocumentId = null;
									loadDocuments();
									loadStats();
								}}
								onUpdated={() => loadDocuments()}
							/>
						</div>
					</div>
				{:else}
					<div class="flex-1 overflow-auto rounded-lg border border-border bg-surface">
						{@render documentTable()}
					</div>
				{/if}
			</div>

		<!-- ================================================================= -->
		<!-- Add Document Tab                                                   -->
		<!-- ================================================================= -->
		{:else if activeTab === 'add'}
			<div class="max-w-3xl">
				<KnowledgeAddDocument onDocumentAdded={handleDocumentAdded} />
			</div>

		<!-- ================================================================= -->
		<!-- Graph Explorer Tab                                                 -->
		<!-- ================================================================= -->
		{:else if activeTab === 'graph'}
			<div class="flex flex-1 flex-col overflow-hidden">
				<!-- KG recompute bar -->
				<div class="flex items-center gap-3 border-b border-border px-4 py-2">
					<button
						type="button"
						onclick={triggerKGRecompute}
						disabled={recomputingKG}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if recomputingKG}
							<Loader2 size={14} class="animate-spin" />
							Recomputing...
						{:else}
							<RefreshCw size={14} />
							Regenerate Knowledge Graph
						{/if}
					</button>
					{#if kgRecomputeMessage}
						<span class="text-xs text-text-secondary">{kgRecomputeMessage}</span>
					{/if}
				</div>
				{#if recomputingKG}
					<div class="h-1.5 w-full overflow-hidden bg-surface">
						<div
							class="h-full rounded-full bg-accent transition-all duration-500"
							style="width: {kgRecomputeProgress}%"
						></div>
					</div>
				{/if}
				<div class="flex-1 overflow-hidden">
					<KnowledgeGraphExplorer />
				</div>
			</div>
		{/if}
	</div>

	<!-- ================================================================= -->
	<!-- Statistics Sidebar                                                  -->
	<!-- ================================================================= -->
	{#if showStats}
		<div
			class="flex w-56 shrink-0 flex-col gap-4 border-l border-border bg-surface-secondary p-4"
		>
			<h3 class="text-xs font-semibold uppercase tracking-wide text-text-secondary">
				Statistics
			</h3>

			<!-- Document counts -->
			<div class="flex flex-col gap-2">
				<div class="flex items-center gap-2">
					<BookOpen size={14} class="text-text-secondary" />
					<span class="text-xs text-text-secondary">Documents</span>
					<span class="ml-auto text-sm font-semibold text-text-primary">
						{documents.length}
					</span>
				</div>

				<div class="flex items-center gap-2">
					<Layers size={14} class="text-text-secondary" />
					<span class="text-xs text-text-secondary">Total Chunks</span>
					<span class="ml-auto text-sm font-semibold text-text-primary">
						{totalChunks}
					</span>
				</div>

				{#if stats}
					<div class="flex items-center gap-2">
						<Network size={14} class="text-text-secondary" />
						<span class="text-xs text-text-secondary">Entities</span>
						<span class="ml-auto text-sm font-semibold text-text-primary">
							{stats.total_entities}
						</span>
					</div>

					<div class="flex items-center gap-2">
						<Hash size={14} class="text-text-secondary" />
						<span class="text-xs text-text-secondary">Relations</span>
						<span class="ml-auto text-sm font-semibold text-text-primary">
							{stats.total_relations}
						</span>
					</div>
				{/if}
			</div>

			<!-- By type breakdown -->
			{#if Object.keys(docCountsByType).length > 0}
				<div class="border-t border-border pt-3">
					<h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
						By Type
					</h4>
					<div class="flex flex-col gap-1.5">
						{#each Object.entries(docCountsByType).sort((a, b) => b[1] - a[1]) as [type, count]}
							<div class="flex items-center gap-2">
								<span
									class="inline-block rounded px-1.5 py-0.5 text-xs font-medium {typeBadgeColors[
										type
									] ?? typeBadgeColors.other}"
								>
									{type}
								</span>
								<span class="ml-auto text-xs text-text-secondary">{count}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Entity type breakdown -->
			{#if stats?.entities_by_type && Object.keys(stats.entities_by_type).length > 0}
				<div class="border-t border-border pt-3">
					<h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
						Entity Types
					</h4>
					<div class="flex flex-col gap-1.5">
						{#each Object.entries(stats.entities_by_type).sort((a, b) => b[1] - a[1]) as [type, count]}
							<div class="flex items-center gap-2">
								<span class="text-xs capitalize text-text-primary">{type}</span>
								<span class="ml-auto text-xs text-text-secondary">{count}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			{#if loadingStats}
				<div class="flex items-center justify-center py-4">
					<Loader2 size={16} class="animate-spin text-text-secondary" />
				</div>
			{/if}
		</div>
	{/if}
</div>

<!-- ===================================================================== -->
<!-- Reusable document table snippet                                        -->
<!-- ===================================================================== -->
{#snippet documentTable()}
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-left text-sm">
				<thead>
					<tr class="border-b border-border bg-surface-secondary">
						<th class="w-10 px-4 py-2">
							<input
								type="checkbox"
								checked={allSelected}
								onchange={toggleSelectAll}
								class="accent-accent"
							/>
						</th>
						<th class="w-8 px-2 py-2"></th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Title</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Status</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Source</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Tags</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Chunks</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Created</th>
						<th class="w-16 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredDocuments as doc, i}
						<tr
							class="cursor-pointer border-b border-border last:border-b-0 transition-colors
								{selectedDocumentId === doc.id ? 'bg-accent/5' : i % 2 === 1 ? 'bg-surface-secondary/50' : ''}
								hover:bg-surface-secondary/80"
							onclick={() => (selectedDocumentId = doc.id)}
						>
							<td class="px-4 py-2" onclick={(e) => e.stopPropagation()}>
								<input
									type="checkbox"
									checked={selectedIds.has(doc.id)}
									onchange={() => toggleSelect(doc.id)}
									class="accent-accent"
								/>
							</td>
							<td class="px-2 py-2 text-text-secondary">
								<FileText size={14} />
							</td>
							<td class="px-4 py-2 font-medium text-text-primary">{doc.title}</td>
							<td class="px-4 py-2">
								<span
									class="rounded px-1.5 py-0.5 text-xs font-medium {typeBadgeColors[
										doc.type
									] ?? typeBadgeColors.other}"
								>
									{doc.type}
								</span>
							</td>
							<td class="px-4 py-2">
								{#if doc.status}
									{@const badge = statusBadge(doc.status)}
									<span class="rounded px-1.5 py-0.5 text-xs font-medium {badge.color}">
										{badge.label}
									</span>
								{/if}
							</td>
							<td class="px-4 py-2 text-text-secondary">{doc.source || '--'}</td>
							<td class="px-4 py-2">
								{#if doc.tags.length > 0}
									<div class="flex flex-wrap gap-1">
										{#each doc.tags.slice(0, 3) as tag}
											<span
												class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
											>
												{tag}
											</span>
										{/each}
										{#if doc.tags.length > 3}
											<span class="text-xs text-text-secondary">
												+{doc.tags.length - 3}
											</span>
										{/if}
									</div>
								{:else}
									<span class="text-xs text-text-secondary">--</span>
								{/if}
							</td>
							<td class="px-4 py-2 text-xs text-text-secondary">
								{doc.chunk_count ?? '--'}
							</td>
							<td class="px-4 py-2 text-xs text-text-secondary">
								{formatDate(doc.created_at)}
							</td>
							<td class="px-4 py-2" onclick={(e) => e.stopPropagation()}>
								<button
									type="button"
									onclick={() => deleteDocument(doc.id)}
									class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
									title="Delete"
								>
									<Trash2 size={14} />
								</button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="10" class="px-4 py-8 text-center text-sm text-text-secondary">
								{searchQuery
									? 'No documents match your search.'
									: 'No documents in the knowledge base. Add one to get started.'}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{/snippet}
