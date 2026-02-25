<!--
  KnowledgeBaseManager.svelte - Knowledge base document management.

  Main admin panel for the knowledge base with three tabs:
  Documents (filterable table), Add Document (multi-method ingestion),
  and Graph Explorer (D3 force graph + list view).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Trash2,
		Loader2,
		FileText,
		BookOpen,
		Plus,
		Network,
		Archive,
		RefreshCw,
		Maximize2
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
		document_type: string;
		source: string | null;
		tags: string[];
		status?: string;
		chunk_count?: number;
		created_at?: string;
		metadata?: Record<string, unknown>;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let activeTab = $state<'documents' | 'add' | 'graph'>('documents');
	let documents = $state<KnowledgeDocument[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let statusFilter = $state('all');

	// Selection
	let selectedDocumentId = $state<string | null>(null);
	let selectedIds = $state<Set<string>>(new Set());

	// Detail panel resize / fullscreen
	let detailWidth = $state(384);
	let isFullscreen = $state(false);
	let isResizing = $state(false);

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
				(d.document_type ?? '').toLowerCase().includes(searchQuery.toLowerCase()) ||
				(d.source ?? '').toLowerCase().includes(searchQuery.toLowerCase()) ||
				d.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
			const matchesStatus = statusFilter === 'all' || d.status === statusFilter;
			return matchesSearch && matchesStatus;
		});
	});

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
	}

	function startResize(e: MouseEvent) {
		e.preventDefault();
		isResizing = true;
		const startX = e.clientX;
		const startWidth = detailWidth;

		function onMouseMove(ev: MouseEvent) {
			// Moving left increases width (detail is on the right)
			const delta = startX - ev.clientX;
			detailWidth = Math.max(300, Math.min(800, startWidth + delta));
		}

		function onMouseUp() {
			isResizing = false;
			window.removeEventListener('mousemove', onMouseMove);
			window.removeEventListener('mouseup', onMouseUp);
		}

		window.addEventListener('mousemove', onMouseMove);
		window.addEventListener('mouseup', onMouseUp);
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
		text: 'bg-accent/10 text-accent',
		markdown: 'bg-purple-500/10 text-purple-500',
		html: 'bg-warning/10 text-warning',
		pdf: 'bg-danger/10 text-danger',
		code: 'bg-success/10 text-success',
		api_spec: 'bg-cyan-500/10 text-cyan-500',
		other: 'bg-text-secondary/10 text-text-secondary'
	};

	function formatDate(dateStr?: string): string {
		if (!dateStr) return '--';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<div class="relative flex h-full">
	<!-- Main content -->
	<div class="flex flex-1 flex-col gap-4 overflow-hidden p-6">
		<!-- Header -->
		<div class="shrink-0">
			<h1 class="text-lg font-semibold text-text-primary">Knowledge Base</h1>
			<p class="text-sm text-text-secondary">
				Manage documents, explore the knowledge graph, and add new content
			</p>
		</div>

		<!-- Error banner -->
		{#if error}
			<div
				class="shrink-0 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
			>
				{error}
			</div>
		{/if}

		<!-- Tab bar -->
		<div class="flex shrink-0 gap-1 border-b border-border">
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
					{#if isFullscreen}
						<!-- Fullscreen detail overlay -->
						<div class="absolute inset-0 z-40 bg-surface">
							<KnowledgeDocumentDetail
								documentId={selectedDocumentId}
								onClose={() => { selectedDocumentId = null; isFullscreen = false; }}
								onDeleted={() => { selectedDocumentId = null; isFullscreen = false; loadDocuments(); }}
								onUpdated={() => loadDocuments()}
								onToggleFullscreen={() => (isFullscreen = !isFullscreen)}
								{isFullscreen}
							/>
						</div>
					{:else}
						<div class="flex flex-1 gap-0 overflow-hidden min-w-0">
							<!-- Table -->
							<div class="min-w-0 flex-1 overflow-auto rounded-lg border border-border bg-surface">
								{@render documentTable()}
							</div>

							<!-- Resize handle -->
							<div
								class="flex w-1 shrink-0 cursor-col-resize items-center justify-center hover:bg-accent/20 transition-colors {isResizing ? 'bg-accent/30' : ''}"
								role="separator"
								aria-orientation="vertical"
								onmousedown={startResize}
							>
								<div class="h-8 w-0.5 rounded-full bg-border"></div>
							</div>

							<!-- Detail panel (resizable, max 60% of container) -->
							<div class="shrink-0 overflow-hidden" style="width: {detailWidth}px; max-width: 60%">
								<KnowledgeDocumentDetail
									documentId={selectedDocumentId}
									onClose={() => (selectedDocumentId = null)}
									onDeleted={() => { selectedDocumentId = null; loadDocuments(); }}
									onUpdated={() => loadDocuments()}
									onToggleFullscreen={() => (isFullscreen = !isFullscreen)}
									{isFullscreen}
								/>
							</div>
						</div>
					{/if}
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
			<div class="min-h-0 flex-1 overflow-y-auto">
				<KnowledgeAddDocument onDocumentAdded={handleDocumentAdded} />
			</div>

		<!-- ================================================================= -->
		<!-- Graph Explorer Tab                                                 -->
		<!-- ================================================================= -->
		{:else if activeTab === 'graph'}
			<div class="flex flex-1 flex-col overflow-hidden">
				<!-- KG recompute bar -->
				<div class="flex shrink-0 items-center gap-3 border-b border-border px-4 py-2">
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
					<div class="h-1.5 w-full shrink-0 overflow-hidden bg-surface">
						<div
							class="h-full rounded-full bg-accent transition-all duration-500"
							style="width: {kgRecomputeProgress}%"
						></div>
					</div>
				{/if}
				<div class="min-h-0 flex-1 overflow-hidden">
					<KnowledgeGraphExplorer />
				</div>
			</div>
		{/if}
	</div>

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
										doc.document_type
									] ?? typeBadgeColors.other}"
								>
									{doc.document_type}
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
							<td colspan="10" class="px-4 py-12 text-center">
								{#if searchQuery || statusFilter !== 'all'}
									<div class="flex flex-col items-center gap-2">
										<Search size={32} class="text-text-secondary/40" />
										<p class="text-sm text-text-secondary">No documents match your search.</p>
									</div>
								{:else}
									<div class="flex flex-col items-center gap-3">
										<div class="rounded-full bg-accent/10 p-3">
											<BookOpen size={32} class="text-accent" />
										</div>
										<div class="flex flex-col items-center gap-1">
											<p class="text-sm font-medium text-text-primary">No documents yet</p>
											<p class="text-sm text-text-secondary">Add your first document to start building your knowledge base.</p>
										</div>
										<button
											type="button"
											onclick={() => (activeTab = 'add')}
											class="mt-1 inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
										>
											<Plus size={14} />
											Add Document
										</button>
									</div>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{/snippet}
