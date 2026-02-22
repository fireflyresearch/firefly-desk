<!--
  KnowledgeBaseManager.svelte - Knowledge base document management.

  Lists documents in a table with upload form and delete actions.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, Trash2, X, Save, Loader2, FileText } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface KnowledgeDocument {
		id: string;
		title: string;
		source: string;
		tags: string[];
		created_at?: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let documents = $state<KnowledgeDocument[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let formData = $state({ title: '', content: '', source: '', tags: '' });
	let saving = $state(false);

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

	$effect(() => {
		loadDocuments();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function openUploadForm() {
		formData = { title: '', content: '', source: '', tags: '' };
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
	}

	async function submitForm() {
		saving = true;
		error = '';
		const payload = {
			title: formData.title,
			content: formData.content,
			source: formData.source,
			tags: formData.tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean)
		};

		try {
			await apiJson('/knowledge/documents', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			showForm = false;
			await loadDocuments();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to upload document';
		} finally {
			saving = false;
		}
	}

	async function deleteDocument(id: string) {
		error = '';
		try {
			await apiJson(`/knowledge/documents/${id}`, { method: 'DELETE' });
			await loadDocuments();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete document';
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function formatDate(dateStr?: string): string {
		if (!dateStr) return '--';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Knowledge Base</h1>
			<p class="text-sm text-text-secondary">Manage documents available to the AI assistant</p>
		</div>
		<button
			type="button"
			onclick={openUploadForm}
			class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			<Plus size={16} />
			Upload Document
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Upload form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">Upload Document</h3>
				<button
					type="button"
					onclick={cancelForm}
					class="text-text-secondary hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<form
				onsubmit={(e) => {
					e.preventDefault();
					submitForm();
				}}
				class="flex flex-col gap-3"
			>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Title</span>
						<input
							type="text"
							bind:value={formData.title}
							required
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Source</span>
						<input
							type="text"
							bind:value={formData.source}
							placeholder="e.g. confluence, manual"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Content</span>
					<textarea
						bind:value={formData.content}
						required
						rows={6}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						placeholder="Paste or type document content..."
					></textarea>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
					<input
						type="text"
						bind:value={formData.tags}
						placeholder="e.g. runbook, onboarding, api-docs"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<div class="flex justify-end gap-2 pt-1">
					<button
						type="button"
						onclick={cancelForm}
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
						Upload
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="rounded-lg border border-border bg-surface">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="w-8 px-4 py-2"></th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Title</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Source</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Tags</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Created</th>
							<th class="w-16 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each documents as doc, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2 text-text-secondary">
									<FileText size={14} />
								</td>
								<td class="px-4 py-2 font-medium text-text-primary">{doc.title}</td>
								<td class="px-4 py-2 text-text-secondary">{doc.source || '--'}</td>
								<td class="px-4 py-2">
									{#if doc.tags.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each doc.tags as tag}
												<span
													class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
												>
													{tag}
												</span>
											{/each}
										</div>
									{:else}
										<span class="text-xs text-text-secondary">--</span>
									{/if}
								</td>
								<td class="px-4 py-2 text-xs text-text-secondary">
									{formatDate(doc.created_at)}
								</td>
								<td class="px-4 py-2">
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
								<td colspan="6" class="px-4 py-8 text-center text-sm text-text-secondary">
									No documents in the knowledge base. Upload one to get started.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
