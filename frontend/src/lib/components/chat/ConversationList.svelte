<!--
  ConversationList.svelte - Sidebar listing previous conversations.

  Reads from the conversations store, allows selecting, renaming,
  and deleting conversations. Groups by date with search/filter.
  Uses Svelte 5 runes.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, MessageSquare, Trash2, Check, X, Search, Sparkles, Pencil } from 'lucide-svelte';
	import {
		conversations,
		activeConversationId,
		loadConversations,
		selectConversation,
		createNewConversation
	} from '$lib/stores/chat.js';
	import {
		renameConversation,
		deleteConversation
	} from '$lib/services/conversations.js';

	let editingId = $state<string | null>(null);
	let editingTitle = $state('');
	let deletingId = $state<string | null>(null);
	let searchQuery = $state('');

	// Load conversations on mount
	$effect(() => {
		loadConversations();
	});

	// -----------------------------------------------------------------------
	// Date grouping
	// -----------------------------------------------------------------------

	const GROUP_ORDER = ['Today', 'Yesterday', 'This Week', 'Older'] as const;

	function getDateGroup(date: Date): string {
		const now = new Date();
		const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
		const yesterday = new Date(today);
		yesterday.setDate(yesterday.getDate() - 1);
		const weekAgo = new Date(today);
		weekAgo.setDate(weekAgo.getDate() - 7);

		if (date >= today) return 'Today';
		if (date >= yesterday) return 'Yesterday';
		if (date >= weekAgo) return 'This Week';
		return 'Older';
	}

	// -----------------------------------------------------------------------
	// Filtered + grouped conversations
	// -----------------------------------------------------------------------

	let filteredConversations = $derived(
		$conversations.filter(
			(c) => !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	let groupedConversations = $derived.by(() => {
		const groups: Record<string, typeof $conversations> = {};
		for (const conv of filteredConversations) {
			const group = getDateGroup(conv.updatedAt);
			if (!groups[group]) groups[group] = [];
			groups[group].push(conv);
		}
		return groups;
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleNew() {
		await createNewConversation();
	}

	async function handleSelect(id: string) {
		if (editingId === id || deletingId === id) return;
		await selectConversation(id);
	}

	function startRename(id: string, currentTitle: string) {
		editingId = id;
		editingTitle = currentTitle;
	}

	async function confirmRename(id: string) {
		const trimmed = editingTitle.trim();
		if (trimmed) {
			try {
				await renameConversation(id, trimmed);
				conversations.update((convs) =>
					convs.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
				);
			} catch (error) {
				console.error('[ConversationList] Rename failed:', error);
			}
		}
		editingId = null;
		editingTitle = '';
	}

	function cancelRename() {
		editingId = null;
		editingTitle = '';
	}

	function handleRenameKeydown(event: KeyboardEvent, id: string) {
		if (event.key === 'Enter') {
			confirmRename(id);
		} else if (event.key === 'Escape') {
			cancelRename();
		}
	}

	function startDelete(id: string) {
		deletingId = id;
	}

	async function confirmDelete(id: string) {
		try {
			await deleteConversation(id);
			conversations.update((convs) => convs.filter((c) => c.id !== id));
			if ($activeConversationId === id) {
				$activeConversationId = null;
			}
		} catch (error) {
			console.error('[ConversationList] Delete failed:', error);
		}
		deletingId = null;
	}

	function cancelDelete() {
		deletingId = null;
	}

	function formatRelativeTime(date: Date): string {
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMs / 3600000);
		const diffDays = Math.floor(diffMs / 86400000);

		if (diffMins < 1) return 'just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return date.toLocaleDateString();
	}
</script>

<div class="flex h-full flex-col">
	<!-- Header area -->
	<div class="space-y-2.5 px-3 pb-3 pt-3">
		<!-- New Conversation button -->
		<button
			type="button"
			onclick={handleNew}
			class="group/new flex w-full items-center justify-center gap-2 rounded-lg bg-ember/10 px-3 py-2.5 text-sm font-medium text-ember transition-all hover:bg-ember/20 active:scale-[0.98]"
		>
			<Plus size={16} class="transition-transform duration-200 group-hover/new:rotate-90" />
			New Conversation
		</button>

		<!-- Search input -->
		<div class="relative">
			<Search
				size={14}
				class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary/60"
			/>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search..."
				class="w-full rounded-lg border border-border/40 bg-surface/60 py-1.5 pl-8 pr-3 text-sm text-text-primary placeholder:text-text-secondary/40 outline-none transition-colors focus:border-accent/40 focus:bg-surface"
			/>
		</div>
	</div>

	<!-- Divider -->
	<div class="mx-3 h-px bg-border/30"></div>

	<!-- Conversation items grouped by date -->
	<div class="flex-1 overflow-y-auto pt-1">
		{#if filteredConversations.length === 0 && $conversations.length === 0}
			<!-- Empty state -->
			<div class="flex flex-col items-center gap-3 px-4 py-12 text-center">
				<div class="flex h-10 w-10 items-center justify-center rounded-full bg-ember/10">
					<Sparkles size={18} class="text-ember" />
				</div>
				<div>
					<p class="text-sm font-medium text-text-primary">No conversations yet</p>
					<p class="mt-1 text-xs text-text-secondary">
						Start a conversation with Ember
					</p>
				</div>
			</div>
		{:else if filteredConversations.length === 0}
			<!-- No search results -->
			<div class="px-4 py-8 text-center text-xs text-text-secondary">
				No conversations match "{searchQuery}"
			</div>
		{:else}
			{#each GROUP_ORDER as groupName}
				{#if groupedConversations[groupName]?.length}
					<!-- Group header -->
					<div class="px-4 pb-1 pt-3">
						<span
							class="text-[10px] font-semibold uppercase tracking-widest text-text-secondary/50"
						>
							{groupName}
						</span>
					</div>

					<!-- Group items -->
					{#each groupedConversations[groupName] as conversation (conversation.id)}
						{@const isActive = $activeConversationId === conversation.id}
						{@const isEditing = editingId === conversation.id}
						{@const isDeleting = deletingId === conversation.id}
						<div
							class="group relative mx-2 mb-0.5 rounded-lg transition-colors
								{isActive
								? 'bg-ember/8'
								: 'hover:bg-surface-hover/60'}"
						>
							<!-- Click area for selection -->
							<button
								type="button"
								onclick={() => handleSelect(conversation.id)}
								class="flex w-full items-start gap-2.5 px-3 py-2.5 text-left"
								disabled={isEditing || isDeleting}
							>
								<span
									class="mt-0.5 shrink-0 {isActive
										? 'text-ember'
										: 'text-text-secondary/60'}"
								>
									<MessageSquare size={14} />
								</span>
								<div class="min-w-0 flex-1">
									{#if isEditing}
										<!-- Inline rename input -->
										<!-- svelte-ignore a11y_autofocus -->
										<input
											type="text"
											bind:value={editingTitle}
											onkeydown={(e) =>
												handleRenameKeydown(e, conversation.id)}
											autofocus
											class="w-full rounded border border-accent/50 bg-surface px-1.5 py-0.5 text-sm text-text-primary outline-none focus:border-accent"
											onclick={(e) => e.stopPropagation()}
										/>
									{:else}
										<div
											class="truncate text-[13px] leading-snug {isActive
												? 'font-semibold text-ember'
												: 'font-medium text-text-primary'}"
											ondblclick={() =>
												startRename(
													conversation.id,
													conversation.title
												)}
											role="textbox"
											tabindex={0}
											onkeydown={(e) => {
												if (e.key === 'Enter')
													startRename(
														conversation.id,
														conversation.title
													);
											}}
										>
											{conversation.title}
										</div>
									{/if}
									<div class="mt-0.5 text-[11px] text-text-secondary/60">
										{formatRelativeTime(conversation.updatedAt)}
									</div>
								</div>
							</button>

							<!-- Action buttons (hover overlay) -->
							{#if isEditing}
								<div class="absolute right-2 top-2 flex items-center gap-0.5">
									<button
										type="button"
										onclick={() => confirmRename(conversation.id)}
										class="flex h-6 w-6 items-center justify-center rounded text-green-500 hover:bg-green-500/10"
										aria-label="Confirm rename"
									>
										<Check size={13} />
									</button>
									<button
										type="button"
										onclick={cancelRename}
										class="flex h-6 w-6 items-center justify-center rounded text-text-secondary hover:bg-surface-hover"
										aria-label="Cancel rename"
									>
										<X size={13} />
									</button>
								</div>
							{:else if isDeleting}
								<div class="absolute right-2 top-2 flex items-center gap-1 rounded-md bg-surface-elevated px-2 py-1 shadow-sm border border-border/50">
									<span class="text-[11px] text-danger">Delete?</span>
									<button
										type="button"
										onclick={() => confirmDelete(conversation.id)}
										class="flex h-5 w-5 items-center justify-center rounded text-danger hover:bg-danger/10"
										aria-label="Confirm delete"
									>
										<Check size={12} />
									</button>
									<button
										type="button"
										onclick={cancelDelete}
										class="flex h-5 w-5 items-center justify-center rounded text-text-secondary hover:bg-surface-hover"
										aria-label="Cancel delete"
									>
										<X size={12} />
									</button>
								</div>
							{:else}
								<div class="absolute right-1.5 top-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
									<button
										type="button"
										onclick={() => startRename(conversation.id, conversation.title)}
										class="flex h-6 w-6 items-center justify-center rounded-md text-text-secondary/70 hover:bg-surface-hover hover:text-text-primary"
										aria-label="Rename conversation"
									>
										<Pencil size={12} />
									</button>
									<button
										type="button"
										onclick={() => startDelete(conversation.id)}
										class="flex h-6 w-6 items-center justify-center rounded-md text-text-secondary/70 hover:bg-danger/10 hover:text-danger"
										aria-label="Delete conversation"
									>
										<Trash2 size={12} />
									</button>
								</div>
							{/if}
						</div>
					{/each}
				{/if}
			{/each}
		{/if}
	</div>
</div>
