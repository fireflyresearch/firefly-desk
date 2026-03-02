<!--
  SystemTagManager.svelte - CRUD interface for system tags.

  Displays tags as colored badges with inline add/edit/delete functionality.
  Used as a standalone component within the CatalogManager.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, Pencil, Trash2, X, Check, Loader2 } from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Tag {
		id: string;
		name: string;
		color: string | null;
		description: string | null;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let {
		onTagsChanged = () => {}
	}: {
		onTagsChanged?: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let tags = $state<Tag[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Add form state
	let newName = $state('');
	let newColor = $state('#6366f1');
	let adding = $state(false);

	// Edit state
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let editColor = $state('');
	let editDescription = $state('');
	let updating = $state(false);

	// Delete state
	let confirmingDeleteId = $state<string | null>(null);
	let deleting = $state(false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadTags() {
		loading = true;
		error = '';
		try {
			tags = await apiJson<Tag[]>('/catalog/tags');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load tags';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadTags();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	async function createTag() {
		if (!newName.trim()) return;
		adding = true;
		error = '';
		try {
			await apiJson('/catalog/tags', {
				method: 'POST',
				body: JSON.stringify({ name: newName.trim(), color: newColor })
			});
			newName = '';
			newColor = '#6366f1';
			await loadTags();
			onTagsChanged();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create tag';
		} finally {
			adding = false;
		}
	}

	function startEdit(tag: Tag) {
		editingId = tag.id;
		editName = tag.name;
		editColor = tag.color ?? '#6366f1';
		editDescription = tag.description ?? '';
	}

	function cancelEdit() {
		editingId = null;
		editName = '';
		editColor = '';
		editDescription = '';
	}

	async function updateTag() {
		if (!editingId || !editName.trim()) return;
		updating = true;
		error = '';
		try {
			await apiJson(`/catalog/tags/${editingId}`, {
				method: 'PUT',
				body: JSON.stringify({
					name: editName.trim(),
					color: editColor,
					description: editDescription.trim() || null
				})
			});
			cancelEdit();
			await loadTags();
			onTagsChanged();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update tag';
		} finally {
			updating = false;
		}
	}

	async function deleteTag(id: string) {
		deleting = true;
		error = '';
		try {
			await apiFetch(`/catalog/tags/${id}`, { method: 'DELETE' });
			confirmingDeleteId = null;
			await loadTags();
			onTagsChanged();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete tag';
		} finally {
			deleting = false;
		}
	}
</script>

<div class="flex flex-col gap-3">
	<!-- Error banner -->
	{#if error}
		<div class="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
			{error}
		</div>
	{/if}

	<!-- Tag list -->
	{#if loading}
		<div class="flex items-center justify-center py-4">
			<Loader2 size={16} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="flex flex-wrap gap-2">
			{#each tags as tag}
				{#if editingId === tag.id}
					<!-- Inline edit form -->
					<div class="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent/5 px-2 py-1">
						<input
							type="color"
							bind:value={editColor}
							class="h-5 w-5 cursor-pointer rounded border-0 bg-transparent p-0"
						/>
						<input
							type="text"
							bind:value={editName}
							class="w-24 rounded border border-border bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-accent"
							placeholder="Tag name"
						/>
						<input
							type="text"
							bind:value={editDescription}
							class="w-32 rounded border border-border bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-accent"
							placeholder="Description (optional)"
						/>
						<button
							type="button"
							onclick={updateTag}
							disabled={updating || !editName.trim()}
							class="rounded p-0.5 text-success hover:bg-success/10 disabled:opacity-50"
							title="Save"
						>
							{#if updating}
								<Loader2 size={12} class="animate-spin" />
							{:else}
								<Check size={12} />
							{/if}
						</button>
						<button
							type="button"
							onclick={cancelEdit}
							class="rounded p-0.5 text-text-secondary hover:bg-surface-hover"
							title="Cancel"
						>
							<X size={12} />
						</button>
					</div>
				{:else}
					<!-- Tag badge -->
					<div class="group flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
						style="background-color: {tag.color ?? '#6366f1'}20; color: {tag.color ?? '#6366f1'};"
					>
						<span
							class="inline-block h-2 w-2 rounded-full"
							style="background-color: {tag.color ?? '#6366f1'};"
						></span>
						{tag.name}
						<button
							type="button"
							onclick={() => startEdit(tag)}
							class="ml-0.5 rounded p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-black/10"
							title="Edit tag"
						>
							<Pencil size={10} />
						</button>
						{#if confirmingDeleteId === tag.id}
							<span class="ml-1 flex items-center gap-1 text-[10px]">
								<span class="text-danger">Delete?</span>
								<button
									type="button"
									onclick={() => deleteTag(tag.id)}
									disabled={deleting}
									class="rounded px-1 py-0.5 text-danger hover:bg-danger/10 disabled:opacity-50"
								>
									Yes
								</button>
								<button
									type="button"
									onclick={() => { confirmingDeleteId = null; }}
									class="rounded px-1 py-0.5 text-text-secondary hover:bg-surface-hover"
								>
									No
								</button>
							</span>
						{:else}
							<button
								type="button"
								onclick={() => { confirmingDeleteId = tag.id; }}
								class="rounded p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-black/10"
								title="Delete tag"
							>
								<Trash2 size={10} />
							</button>
						{/if}
					</div>
				{/if}
			{/each}

			{#if tags.length === 0}
				<p class="text-xs text-text-secondary">No tags defined yet.</p>
			{/if}
		</div>

		<!-- Add tag form -->
		<div class="flex items-center gap-2">
			<input
				type="color"
				bind:value={newColor}
				class="h-6 w-6 cursor-pointer rounded border-0 bg-transparent p-0"
				title="Tag color"
			/>
			<input
				type="text"
				bind:value={newName}
				placeholder="New tag name..."
				class="w-40 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-text-primary outline-none focus:border-accent"
				onkeydown={(e) => { if (e.key === 'Enter') createTag(); }}
			/>
			<button
				type="button"
				onclick={createTag}
				disabled={adding || !newName.trim()}
				class="inline-flex items-center gap-1 rounded-md border border-dashed border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
			>
				{#if adding}
					<Loader2 size={12} class="animate-spin" />
				{:else}
					<Plus size={12} />
				{/if}
				Add
			</button>
		</div>
	{/if}
</div>
