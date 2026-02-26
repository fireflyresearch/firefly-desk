<!--
  Memories settings page - View and manage saved user memories.

  Displays a searchable list of memories with category badges,
  content preview, and delete functionality.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Trash2, Loader2, Search, Brain, Tag } from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	interface UserMemory {
		id: string;
		user_id: string;
		content: string;
		category: string;
		source: string;
		created_at: string | null;
		updated_at: string | null;
	}

	let memories = $state<UserMemory[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let categoryFilter = $state('all');
	let showAddForm = $state(false);
	let newContent = $state('');
	let newCategory = $state('general');
	let creating = $state(false);

	let filteredMemories = $derived(
		memories.filter((m) => {
			const matchesSearch =
				!searchQuery.trim() ||
				m.content.toLowerCase().includes(searchQuery.toLowerCase());
			const matchesCategory = categoryFilter === 'all' || m.category === categoryFilter;
			return matchesSearch && matchesCategory;
		})
	);

	const categoryColors: Record<string, string> = {
		general: 'bg-text-secondary/10 text-text-secondary',
		preference: 'bg-accent/10 text-accent',
		fact: 'bg-success/10 text-success',
		workflow: 'bg-purple-500/10 text-purple-500'
	};

	async function loadMemories() {
		loading = true;
		error = '';
		try {
			memories = await apiJson<UserMemory[]>('/memory');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load memories';
		} finally {
			loading = false;
		}
	}

	async function deleteMemory(id: string) {
		if (!confirm('Delete this memory?')) return;
		try {
			await apiFetch(`/memory/${id}`, { method: 'DELETE' });
			memories = memories.filter((m) => m.id !== id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete memory';
		}
	}

	async function createMemory() {
		if (!newContent.trim()) return;
		creating = true;
		try {
			const memory = await apiJson<UserMemory>('/memory', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: newContent.trim(), category: newCategory })
			});
			memories = [memory, ...memories];
			newContent = '';
			newCategory = 'general';
			showAddForm = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create memory';
		} finally {
			creating = false;
		}
	}

	function formatDate(dateStr: string | null): string {
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

	$effect(() => {
		loadMemories();
	});
</script>

<div class="mx-auto max-w-3xl p-6">
	<!-- Header -->
	<div class="mb-6 flex items-center justify-between">
		<div class="flex items-center gap-3">
			<div class="rounded-lg bg-accent/10 p-2">
				<Brain size={20} class="text-accent" />
			</div>
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Memories</h1>
				<p class="text-sm text-text-secondary">
					Things the agent has remembered about you across conversations
				</p>
			</div>
		</div>
		<button
			type="button"
			onclick={() => (showAddForm = !showAddForm)}
			class="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-surface-hover"
		>
			{showAddForm ? 'Cancel' : '+ Add Memory'}
		</button>
	</div>

	{#if showAddForm}
		<div class="mb-4 rounded-lg border border-accent/30 bg-accent/5 p-4">
			<textarea
				bind:value={newContent}
				placeholder="What should the agent remember? e.g., 'I prefer concise responses' or 'Our team uses React with TypeScript'"
				rows="3"
				class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-secondary/50 focus:border-accent"
			></textarea>
			<div class="mt-3 flex items-center justify-between">
				<select
					bind:value={newCategory}
					class="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				>
					<option value="general">General</option>
					<option value="preference">Preference</option>
					<option value="fact">Fact</option>
					<option value="workflow">Workflow</option>
				</select>
				<button
					type="button"
					onclick={createMemory}
					disabled={creating || !newContent.trim()}
					class="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
				>
					{#if creating}
						<Loader2 size={14} class="inline animate-spin" /> Saving...
					{:else}
						Save Memory
					{/if}
				</button>
			</div>
		</div>
	{/if}

	{#if error}
		<div
			class="mb-4 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			{error}
		</div>
	{/if}

	<!-- Search and filter -->
	<div class="mb-4 flex items-center gap-3">
		<div class="relative flex-1">
			<Search size={14} class="absolute top-1/2 left-3 -translate-y-1/2 text-text-secondary" />
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search memories..."
				class="w-full rounded-md border border-border bg-surface py-1.5 pr-3 pl-8 text-sm text-text-primary outline-none focus:border-accent"
			/>
		</div>
		<select
			bind:value={categoryFilter}
			class="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
		>
			<option value="all">All categories</option>
			<option value="general">General</option>
			<option value="preference">Preference</option>
			<option value="fact">Fact</option>
			<option value="workflow">Workflow</option>
		</select>
	</div>

	<!-- Memory list -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if filteredMemories.length === 0}
		<div class="flex flex-col items-center gap-3 py-12">
			<div class="rounded-full bg-accent/10 p-3">
				<Brain size={32} class="text-accent" />
			</div>
			<p class="text-sm text-text-secondary">
				{#if searchQuery || categoryFilter !== 'all'}
					No memories match your search.
				{:else}
					No memories saved yet. The agent will remember important things as you chat.
				{/if}
			</p>
		</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each filteredMemories as memory (memory.id)}
				<div
					class="group flex items-start gap-3 rounded-lg border border-border bg-surface p-3 transition-colors hover:border-border/80"
				>
					<div class="flex-1">
						<p class="text-sm text-text-primary">{memory.content}</p>
						<div class="mt-2 flex items-center gap-2">
							<span
								class="rounded-full px-2 py-0.5 text-[10px] font-medium {categoryColors[memory.category] ?? categoryColors.general}"
							>
								{memory.category}
							</span>
							<span class="flex items-center gap-1 text-[10px] text-text-secondary">
								<Tag size={10} />
								{memory.source}
							</span>
							<span class="text-[10px] text-text-secondary">
								{formatDate(memory.created_at)}
							</span>
						</div>
					</div>
					<button
						type="button"
						onclick={() => deleteMemory(memory.id)}
						class="shrink-0 rounded p-1.5 text-text-secondary opacity-0 transition-all hover:bg-danger/10 hover:text-danger group-hover:opacity-100"
						title="Delete memory"
					>
						<Trash2 size={14} />
					</button>
				</div>
			{/each}
		</div>

		<p class="mt-4 text-center text-xs text-text-secondary">
			{filteredMemories.length} of {memories.length} memories
		</p>
	{/if}
</div>
