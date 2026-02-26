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
		Maximize2,
		Settings,
		CheckCircle,
		AlertTriangle,
		XCircle,
		Save
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
		workspace_ids?: string[];
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let activeTab = $state<'documents' | 'add' | 'graph' | 'settings'>('documents');
	let documents = $state<KnowledgeDocument[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let statusFilter = $state('all');
	let workspaces = $state<{id: string; name: string}[]>([]);
	let workspaceFilter = $state('all');

	// Selection
	let selectedDocumentId = $state<string | null>(null);
	let selectedIds = $state<Set<string>>(new Set());

	// Pagination
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Detail panel resize / fullscreen
	let detailWidth = $state(384);
	let isFullscreen = $state(false);
	let isResizing = $state(false);

	// KG recompute
	let recomputingKG = $state(false);
	let kgRecomputeMessage = $state('');
	let kgRecomputeProgress = $state(0);

	// Knowledge quality settings
	let settingsLoading = $state(false);
	let settingsSaving = $state(false);
	let settingsSaved = $state(false);
	let settingsChunkingMode = $state<'auto' | 'structural' | 'fixed'>('auto');
	let settingsChunkSize = $state(500);
	let settingsChunkOverlap = $state(50);
	let settingsAutoKgExtract = $state(true);

	// Embedding status
	let embeddingStatus = $state<'ok' | 'warning' | 'error' | null>(null);
	let embeddingStatusMessage = $state('');

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
			const matchesWorkspace = workspaceFilter === 'all' || (d.workspace_ids ?? []).includes(workspaceFilter);
			return matchesSearch && matchesStatus && matchesWorkspace;
		});
	});

	let totalPages = $derived(Math.ceil(filteredDocuments.length / pageSize));
	let paginatedDocuments = $derived(
		filteredDocuments.slice((currentPage - 1) * pageSize, currentPage * pageSize)
	);

	let allSelected = $derived(
		paginatedDocuments.length > 0 && paginatedDocuments.every((d) => selectedIds.has(d.id))
	);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadWorkspaces() {
		try {
			const result = await apiJson<{id: string; name: string; description: string; icon: string; color: string; roles: string[]; users: string[]}[]>('/workspaces');
			workspaces = result.map((w) => ({ id: w.id, name: w.name }));
		} catch {
			// Workspaces are optional — silently ignore errors
		}
	}

	async function loadDocuments() {
		loading = true;
		error = '';
		try {
			const url = workspaceFilter !== 'all'
				? `/knowledge/documents?workspace_id=${workspaceFilter}`
				: '/knowledge/documents';
			documents = await apiJson<KnowledgeDocument[]>(url);
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

	async function loadKnowledgeSettings() {
		settingsLoading = true;
		try {
			const config = await apiJson<{
				chunk_size: number;
				chunk_overlap: number;
				chunking_mode: string;
				auto_kg_extract: boolean;
			}>('/settings/knowledge');
			settingsChunkSize = config.chunk_size;
			settingsChunkOverlap = config.chunk_overlap;
			settingsChunkingMode = config.chunking_mode as typeof settingsChunkingMode;
			settingsAutoKgExtract = config.auto_kg_extract;
		} catch {
			// Use defaults on error
		} finally {
			settingsLoading = false;
		}
	}

	async function loadEmbeddingStatus() {
		try {
			const result = await apiJson<{ status: string; message: string; dimensions?: number }>(
				'/settings/embedding/status'
			);
			embeddingStatus = result.status as typeof embeddingStatus;
			embeddingStatusMessage = result.message;
		} catch {
			embeddingStatus = 'error';
			embeddingStatusMessage = 'Unable to check embedding status';
		}
	}

	async function saveKnowledgeSettings() {
		settingsSaving = true;
		settingsSaved = false;
		error = '';
		try {
			await apiJson('/settings/knowledge', {
				method: 'PUT',
				body: JSON.stringify({
					chunk_size: settingsChunkSize,
					chunk_overlap: settingsChunkOverlap,
					chunking_mode: settingsChunkingMode,
					auto_kg_extract: settingsAutoKgExtract
				})
			});
			settingsSaved = true;
			setTimeout(() => (settingsSaved = false), 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save settings';
		} finally {
			settingsSaving = false;
		}
	}

	$effect(() => {
		loadWorkspaces();
		loadDocuments();
	});

	$effect(() => {
		void searchQuery;
		void statusFilter;
		void workspaceFilter;
		currentPage = 1;
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
			const next = new Set(selectedIds);
			for (const d of paginatedDocuments) next.delete(d.id);
			selectedIds = next;
		} else {
			const next = new Set(selectedIds);
			for (const d of paginatedDocuments) next.add(d.id);
			selectedIds = next;
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
			<button
				type="button"
				onclick={() => { activeTab = 'settings'; loadKnowledgeSettings(); loadEmbeddingStatus(); }}
				class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
					{activeTab === 'settings'
					? 'border-b-2 border-accent text-accent'
					: 'text-text-secondary hover:text-text-primary'}"
			>
				<Settings size={14} />
				Settings
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

					<!-- Workspace filter dropdown -->
					<select
						bind:value={workspaceFilter}
						class="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						<option value="all">All workspaces</option>
						{#each workspaces as ws}
							<option value={ws.id}>{ws.name}</option>
						{/each}
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
								{workspaces}
							/>
						</div>
					{:else}
						<div class="flex flex-1 gap-0 overflow-hidden min-w-0">
							<!-- Table -->
							<div class="min-w-0 flex-1 overflow-hidden rounded-lg border border-border bg-surface">
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
									{workspaces}
								/>
							</div>
						</div>
					{/if}
				{:else}
					<div class="flex-1 overflow-hidden rounded-lg border border-border bg-surface">
						{@render documentTable()}
					</div>
				{/if}
			</div>

		<!-- ================================================================= -->
		<!-- Add Document Tab                                                   -->
		<!-- ================================================================= -->
		{:else if activeTab === 'add'}
			<div class="min-h-0 flex-1 overflow-y-auto">
				<KnowledgeAddDocument onDocumentAdded={handleDocumentAdded} {workspaces} />
			</div>

		<!-- ================================================================= -->
		<!-- Graph Explorer Tab                                                 -->
		<!-- ================================================================= -->
		{:else if activeTab === 'graph'}
			<div class="min-h-0 flex-1 overflow-hidden">
				<KnowledgeGraphExplorer
					onRegenerate={triggerKGRecompute}
					regenerating={recomputingKG}
					regenerateMessage={kgRecomputeMessage}
					regenerateProgress={kgRecomputeProgress}
				/>
			</div>

		<!-- ================================================================= -->
		<!-- Settings Tab                                                       -->
		<!-- ================================================================= -->
		{:else if activeTab === 'settings'}
			<div class="min-h-0 flex-1 overflow-y-auto">
				{#if settingsLoading}
					<div class="flex items-center justify-center py-12">
						<Loader2 size={24} class="animate-spin text-text-secondary" />
					</div>
				{:else}
					<div class="mx-auto max-w-2xl space-y-6 py-2">
						<!-- Embedding Status -->
						{#if embeddingStatus}
							<div
								class="flex items-start gap-3 rounded-lg border px-4 py-3
									{embeddingStatus === 'ok'
									? 'border-success/30 bg-success/5'
									: embeddingStatus === 'warning'
									? 'border-warning/30 bg-warning/5'
									: 'border-danger/30 bg-danger/5'}"
							>
								{#if embeddingStatus === 'ok'}
									<CheckCircle size={18} class="mt-0.5 shrink-0 text-success" />
								{:else if embeddingStatus === 'warning'}
									<AlertTriangle size={18} class="mt-0.5 shrink-0 text-warning" />
								{:else}
									<XCircle size={18} class="mt-0.5 shrink-0 text-danger" />
								{/if}
								<div>
									<span class="block text-sm font-medium
										{embeddingStatus === 'ok' ? 'text-success' : embeddingStatus === 'warning' ? 'text-warning' : 'text-danger'}">
										Embedding Status: {embeddingStatus === 'ok' ? 'Active' : embeddingStatus === 'warning' ? 'Warning' : 'Error'}
									</span>
									<span class="block text-xs text-text-secondary">{embeddingStatusMessage}</span>
								</div>
							</div>
						{/if}

						<!-- Chunking Mode -->
						<section>
							<h3 class="mb-3 text-sm font-semibold text-text-primary">Chunking Mode</h3>
							<div class="grid grid-cols-3 gap-3">
								{#each [
									{ value: 'auto', label: 'Auto', desc: 'Detect headings in Markdown, fall back to fixed for plain text' },
									{ value: 'structural', label: 'Structural', desc: 'Always split on H1/H2 headings, sub-chunk large sections' },
									{ value: 'fixed', label: 'Fixed', desc: 'Sliding window chunking with overlap' }
								] as mode}
									<button
										type="button"
										onclick={() => (settingsChunkingMode = mode.value as typeof settingsChunkingMode)}
										class="rounded-lg border px-4 py-3 text-left transition-all
											{settingsChunkingMode === mode.value
											? 'border-accent bg-accent/5 shadow-sm'
											: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
									>
										<span class="block text-sm font-medium
											{settingsChunkingMode === mode.value ? 'text-accent' : 'text-text-primary'}">
											{mode.label}
										</span>
										<span class="mt-1 block text-[11px] leading-tight text-text-secondary">{mode.desc}</span>
									</button>
								{/each}
							</div>
						</section>

						<!-- Chunk Size & Overlap -->
						<section>
							<h3 class="mb-3 text-sm font-semibold text-text-primary">Chunk Parameters</h3>
							<div class="grid grid-cols-2 gap-4">
								<div>
									<label for="settings-chunk-size" class="mb-1.5 block text-xs font-medium text-text-secondary">
										Chunk Size <span class="text-text-secondary/60">(chars)</span>
									</label>
									<input
										id="settings-chunk-size"
										type="number"
										bind:value={settingsChunkSize}
										min={100}
										max={2000}
										step={50}
										class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-accent focus:outline-none"
									/>
								</div>
								<div>
									<label for="settings-chunk-overlap" class="mb-1.5 block text-xs font-medium text-text-secondary">
										Chunk Overlap <span class="text-text-secondary/60">(chars)</span>
									</label>
									<input
										id="settings-chunk-overlap"
										type="number"
										bind:value={settingsChunkOverlap}
										min={0}
										max={500}
										step={10}
										class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-accent focus:outline-none"
									/>
								</div>
							</div>
						</section>

						<!-- Auto KG Extract -->
						<section>
							<div class="flex items-center justify-between rounded-lg border border-border px-4 py-3">
								<div>
									<span class="block text-sm font-medium text-text-primary">Auto KG Extraction</span>
									<span class="block text-xs text-text-secondary">
										Automatically extract entities and relations when new documents are indexed
									</span>
								</div>
								<button
									type="button"
									role="switch"
									aria-checked={settingsAutoKgExtract}
									onclick={() => (settingsAutoKgExtract = !settingsAutoKgExtract)}
									class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
										{settingsAutoKgExtract ? 'bg-accent' : 'bg-border'}"
								>
									<span
										class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform
											{settingsAutoKgExtract ? 'translate-x-5' : 'translate-x-0'}"
									/>
								</button>
							</div>
						</section>

						<!-- Info & Save -->
						<div class="flex items-center justify-between border-t border-border pt-4">
							<p class="text-xs text-text-secondary">
								Changes apply to newly indexed documents. Use bulk re-index to apply to existing documents.
							</p>
							<button
								type="button"
								onclick={saveKnowledgeSettings}
								disabled={settingsSaving}
								class="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
							>
								{#if settingsSaving}
									<Loader2 size={16} class="animate-spin" />
									Saving...
								{:else if settingsSaved}
									<CheckCircle size={16} />
									Saved
								{:else}
									<Save size={16} />
									Save Settings
								{/if}
							</button>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

</div>

<!-- ===================================================================== -->
<!-- Reusable document table snippet                                        -->
<!-- ===================================================================== -->
{#snippet documentTable()}
	<div class="flex h-full flex-col overflow-hidden">
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="min-h-0 flex-1 overflow-auto">
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
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Workspace</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Source</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Tags</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Chunks</th>
						<th class="px-4 py-2 text-xs font-medium text-text-secondary">Created</th>
						<th class="w-16 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each paginatedDocuments as doc, i}
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
							<td class="px-4 py-2">
								{#if (doc.workspace_ids ?? []).length > 0}
									<div class="flex flex-wrap gap-1">
										{#each (doc.workspace_ids ?? []).slice(0, 2) as wid}
											<span class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary">
												{workspaces.find((w) => w.id === wid)?.name ?? wid}
											</span>
										{/each}
										{#if (doc.workspace_ids ?? []).length > 2}
											<span class="text-xs text-text-secondary">+{(doc.workspace_ids ?? []).length - 2}</span>
										{/if}
									</div>
								{:else}
									<span class="text-xs text-text-secondary">--</span>
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
							<td colspan="11" class="px-4 py-12 text-center">
								{#if searchQuery || statusFilter !== 'all' || workspaceFilter !== 'all'}
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

		<!-- Pagination footer -->
		{#if filteredDocuments.length > pageSize}
			<div class="flex items-center justify-between border-t border-border px-4 py-2">
				<span class="text-xs text-text-secondary">
					{(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filteredDocuments.length)} of {filteredDocuments.length}
				</span>
				<div class="flex items-center gap-1">
					<button
						type="button"
						disabled={currentPage <= 1}
						onclick={() => currentPage--}
						class="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-40"
					>
						Previous
					</button>
					<span class="px-2 text-xs text-text-secondary">Page {currentPage} of {totalPages}</span>
					<button
						type="button"
						disabled={currentPage >= totalPages}
						onclick={() => currentPage++}
						class="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-40"
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	{/if}
	</div>
{/snippet}
