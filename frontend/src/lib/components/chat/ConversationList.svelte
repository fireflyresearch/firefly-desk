<!--
  ConversationList.svelte - Sidebar listing previous conversations.

  Reads from the conversations store, allows selecting, renaming,
  and deleting conversations. Groups by date with search/filter.
  Uses Svelte 5 runes.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, MessageSquare, Trash2, Check, X, Search, Sparkles } from 'lucide-svelte';
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
	<!-- Header area: New Conversation button + search -->
	<div class="space-y-2 border-b border-border/50 px-3 py-3">
		<!-- New Conversation button -->
		<button
			type="button"
			onclick={handleNew}
			class="group/new flex w-full items-center gap-2 rounded-lg border border-border/50 px-3 py-2.5 text-sm font-medium text-text-secondary transition-all hover:border-ember/40 hover:bg-ember/5 hover:text-text-primary"
		>
			<Plus size={16} class="transition-transform group-hover/new:rotate-90" />
			New Conversation
		</button>

		<!-- Search input -->
		<div class="relative">
			<Search
				size={14}
				class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary"
			/>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search conversations..."
				class="w-full rounded-lg border border-border/50 bg-surface/50 py-1.5 pl-8 pr-3 text-sm text-text-primary placeholder:text-text-secondary/50 outline-none transition-colors focus:border-accent/50 focus:bg-surface"
			/>
		</div>
	</div>

	<!-- Conversation items grouped by date -->
	<div class="flex-1 overflow-y-auto">
		{#if filteredConversations.length === 0 && $conversations.length === 0}
			<!-- Empty state -->
			<div class="flex flex-col items-center gap-2 px-3 py-10 text-center">
				<Sparkles size={20} class="text-ember/60" />
				<span class="text-sm text-text-secondary">
					Start a conversation with Ember
				</span>
			</div>
		{:else if filteredConversations.length === 0}
			<!-- No search results -->
			<div class="px-3 py-6 text-center text-xs text-text-secondary">
				No conversations match your search
			</div>
		{:else}
			{#each GROUP_ORDER as groupName}
				{#if groupedConversations[groupName]?.length}
					<!-- Group header -->
					<div class="px-3 py-1.5 first:pt-2">
						<span
							class="text-[11px] font-semibold uppercase tracking-wider text-text-secondary/70"
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
							class="group relative flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition-colors
								{isActive
								? 'border-l-2 border-l-ember bg-ember/5'
								: 'border-l-2 border-l-transparent hover:bg-surface-hover/50'}"
						>
							<!-- Click area for selection -->
							<button
								type="button"
								onclick={() => handleSelect(conversation.id)}
								class="flex min-w-0 flex-1 items-start gap-2.5"
								disabled={isEditing || isDeleting}
							>
								<span
									class="mt-0.5 shrink-0 {isActive
										? 'text-ember'
										: 'text-text-secondary'}"
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
											class="w-full rounded border border-border bg-surface px-1 py-0.5 text-sm text-text-primary outline-none focus:border-accent"
											onclick={(e) => e.stopPropagation()}
										/>
									{:else}
										<div
											class="truncate text-sm font-medium {isActive
												? 'text-ember'
												: 'text-text-primary'}"
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
									<div class="mt-0.5 text-xs text-text-secondary">
										{formatRelativeTime(conversation.updatedAt)}
									</div>
								</div>
							</button>

							<!-- Action buttons -->
							{#if isEditing}
								<div class="flex items-center gap-1">
									<button
										type="button"
										onclick={() => confirmRename(conversation.id)}
										class="flex h-6 w-6 items-center justify-center rounded text-green-500 hover:bg-green-500/10"
										aria-label="Confirm rename"
									>
										<Check size={14} />
									</button>
									<button
										type="button"
										onclick={cancelRename}
										class="flex h-6 w-6 items-center justify-center rounded text-text-secondary hover:bg-surface-hover"
										aria-label="Cancel rename"
									>
										<X size={14} />
									</button>
								</div>
							{:else if isDeleting}
								<div class="flex items-center gap-1">
									<span class="text-xs text-text-secondary">Delete?</span>
									<button
										type="button"
										onclick={() => confirmDelete(conversation.id)}
										class="flex h-6 w-6 items-center justify-center rounded text-red-500 hover:bg-red-500/10"
										aria-label="Confirm delete"
									>
										<Check size={14} />
									</button>
									<button
										type="button"
										onclick={cancelDelete}
										class="flex h-6 w-6 items-center justify-center rounded text-text-secondary hover:bg-surface-hover"
										aria-label="Cancel delete"
									>
										<X size={14} />
									</button>
								</div>
							{:else}
								<button
									type="button"
									onclick={() => startDelete(conversation.id)}
									class="flex h-6 w-6 shrink-0 items-center justify-center rounded text-text-secondary opacity-0 transition-opacity hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
									aria-label="Delete conversation"
								>
									<Trash2 size={14} />
								</button>
							{/if}
						</div>
					{/each}
				{/if}
			{/each}
		{/if}
	</div>
</div>
