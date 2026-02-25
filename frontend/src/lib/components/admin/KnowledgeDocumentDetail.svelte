<!--
  KnowledgeDocumentDetail.svelte - Document detail view and editor.

  Displays full document details with editable metadata fields.
  Used as an expandable detail panel in the Documents tab.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		Save,
		Loader2,
		Trash2,
		FileText,
		Tag,
		Clock,
		Hash,
		Pencil,
		CheckCircle2,
		AlertCircle,
		RefreshCw
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import RichEditor from '$lib/components/shared/RichEditor.svelte';
	import MarkdownContent from '$lib/components/shared/MarkdownContent.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface KnowledgeDocument {
		id: string;
		title: string;
		type: string;
		source: string;
		content?: string;
		tags: string[];
		status?: string;
		chunk_count?: number;
		created_at?: string;
		updated_at?: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		documentId: string;
		onClose: () => void;
		onDeleted?: () => void;
		onUpdated?: () => void;
	}

	let { documentId, onClose, onDeleted, onUpdated }: Props = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let doc = $state<KnowledgeDocument | null>(null);
	let loading = $state(true);
	let error = $state('');
	let success = $state('');
	let editing = $state(false);
	let saving = $state(false);
	let deleting = $state(false);

	let reindexing = $state(false);

	// Edit form
	let editForm = $state({
		title: '',
		source: '',
		tags: '',
		content: ''
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadDocument() {
		loading = true;
		error = '';
		try {
			doc = await apiJson<KnowledgeDocument>(`/knowledge/documents/${documentId}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load document';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadDocument();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function startEditing() {
		if (!doc) return;
		editForm = {
			title: doc.title,
			source: doc.source || '',
			tags: doc.tags.join(', '),
			content: doc.content || ''
		};
		editing = true;
	}

	function cancelEditing() {
		editing = false;
	}

	async function saveEdits() {
		saving = true;
		error = '';
		success = '';

		const contentChanged = editForm.content !== (doc?.content || '');
		const payload: Record<string, any> = {
			title: editForm.title,
			tags: editForm.tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean)
		};
		if (contentChanged) {
			payload.content = editForm.content;
			payload.status = 'draft';
		}

		try {
			await apiJson(`/knowledge/documents/${documentId}`, {
				method: 'PUT',
				body: JSON.stringify(payload)
			});
			success = contentChanged
				? 'Document updated. Re-index to apply changes.'
				: 'Document updated.';
			editing = false;
			await loadDocument();
			onUpdated?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update document';
		} finally {
			saving = false;
		}
	}

	async function deleteDocument() {
		if (!confirm('Delete this document? This cannot be undone.')) return;
		deleting = true;
		error = '';

		try {
			await apiFetch(`/knowledge/documents/${documentId}`, { method: 'DELETE' });
			onDeleted?.();
			onClose();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete document';
			deleting = false;
		}
	}

	async function reindexDocument() {
		if (!doc) return;
		reindexing = true;
		error = '';
		try {
			await apiJson('/knowledge/documents/bulk-reindex', {
				method: 'POST',
				body: JSON.stringify({ document_ids: [documentId] })
			});
			success = 'Document queued for re-indexing.';
			await loadDocument();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to re-index';
		} finally {
			reindexing = false;
		}
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
		return d.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<div class="flex h-full flex-col rounded-lg border border-border bg-surface">
	<!-- Header -->
	<div class="flex items-center justify-between border-b border-border px-4 py-3">
		<div class="flex items-center gap-2">
			<FileText size={16} class="text-accent" />
			<h3 class="text-sm font-semibold text-text-primary">Document Detail</h3>
		</div>
		<div class="flex items-center gap-1">
			{#if !editing}
				<button
					type="button"
					onclick={reindexDocument}
					disabled={reindexing}
					class="rounded p-1.5 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent"
					title="Re-index"
				>
					{#if reindexing}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<RefreshCw size={14} />
					{/if}
				</button>
				<button
					type="button"
					onclick={startEditing}
					class="rounded p-1.5 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent"
					title="Edit"
				>
					<Pencil size={14} />
				</button>
			{/if}
			<button
				type="button"
				onclick={deleteDocument}
				disabled={deleting}
				class="rounded p-1.5 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
				title="Delete"
			>
				{#if deleting}
					<Loader2 size={14} class="animate-spin" />
				{:else}
					<Trash2 size={14} />
				{/if}
			</button>
			<button
				type="button"
				onclick={onClose}
				class="rounded p-1.5 text-text-secondary transition-colors hover:text-text-primary"
				title="Close"
			>
				<X size={14} />
			</button>
		</div>
	</div>

	<!-- Body -->
	<div class="flex-1 overflow-y-auto p-4">
		{#if loading}
			<div class="flex items-center justify-center py-12">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else if error}
			<div
				class="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
			>
				<AlertCircle size={16} />
				{error}
			</div>
		{:else if doc}
			{#if success}
				<div
					class="mb-3 flex items-center gap-2 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success"
				>
					<CheckCircle2 size={14} />
					{success}
				</div>
			{/if}

			{#if editing}
				<!-- Edit form -->
				<form
					onsubmit={(e) => {
						e.preventDefault();
						saveEdits();
					}}
					class="flex flex-col gap-3"
				>
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Title</span>
						<input
							type="text"
							bind:value={editForm.title}
							required
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Source</span>
						<input
							type="text"
							bind:value={editForm.source}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
						<input
							type="text"
							bind:value={editForm.tags}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<div class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Content</span>
						<RichEditor
							value={editForm.content}
							placeholder="Enter document content..."
							mode="full"
							minHeight="300px"
							onchange={(md) => (editForm.content = md)}
						/>
					</div>

					<div class="flex justify-end gap-2 pt-1">
						<button
							type="button"
							onclick={cancelEditing}
							class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
						>
							Cancel
						</button>
						<button
							type="submit"
							disabled={saving}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if saving}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Save size={14} />
							{/if}
							Save Changes
						</button>
					</div>
				</form>
			{:else}
				<!-- Read-only view -->
				<div class="flex flex-col gap-4">
					<!-- Title and type -->
					<div>
						<h2 class="text-base font-semibold text-text-primary">{doc.title}</h2>
						<div class="mt-1.5 flex items-center gap-1.5">
							<span
								class="inline-block rounded px-1.5 py-0.5 text-xs font-medium {typeBadgeColors[
									doc.type
								] ?? typeBadgeColors.other}"
							>
								{doc.type}
							</span>
							{#if doc.status}
								{@const badge = statusBadge(doc.status)}
								<span
									class="inline-block rounded px-1.5 py-0.5 text-xs font-medium {badge.color}"
								>
									{badge.label}
								</span>
							{/if}
						</div>
					</div>

					<!-- Metadata grid -->
					<div class="grid grid-cols-2 gap-3">
						<div class="flex flex-col gap-1 rounded-md bg-surface-secondary/50 px-3 py-2">
							<span class="flex items-center gap-1.5 text-xs text-text-secondary">
								<Tag size={12} />
								Source
							</span>
							<span class="text-sm font-medium text-text-primary">{doc.source || '--'}</span>
						</div>

						<div class="flex flex-col gap-1 rounded-md bg-surface-secondary/50 px-3 py-2">
							<span class="flex items-center gap-1.5 text-xs text-text-secondary">
								<Hash size={12} />
								Chunks
							</span>
							<span class="text-sm font-medium text-text-primary">{doc.chunk_count ?? '--'}</span>
						</div>

						<div class="flex flex-col gap-1 rounded-md bg-surface-secondary/50 px-3 py-2">
							<span class="flex items-center gap-1.5 text-xs text-text-secondary">
								<Clock size={12} />
								Created
							</span>
							<span class="text-sm font-medium text-text-primary">{formatDate(doc.created_at)}</span>
						</div>

						<div class="flex flex-col gap-1 rounded-md bg-surface-secondary/50 px-3 py-2">
							<span class="flex items-center gap-1.5 text-xs text-text-secondary">
								<Clock size={12} />
								Updated
							</span>
							<span class="text-sm font-medium text-text-primary">{formatDate(doc.updated_at)}</span>
						</div>
					</div>

					<!-- Tags -->
					{#if doc.tags.length > 0}
						<div class="flex flex-col gap-1.5">
							<span class="text-xs font-medium text-text-secondary">Tags</span>
							<div class="flex flex-wrap gap-1.5">
								{#each doc.tags as tag}
									<span
										class="rounded-full bg-surface-secondary px-2.5 py-0.5 text-xs text-text-secondary"
									>
										{tag}
									</span>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Content preview -->
					{#if doc.content}
						<div class="flex min-h-0 flex-1 flex-col gap-1.5">
							<span class="text-xs font-medium text-text-secondary">Content Preview</span>
							<div class="min-h-0 flex-1">
								<MarkdownContent content={doc.content} />
							</div>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>
