<!--
  ConversationList.svelte - Sidebar listing previous conversations.

  Groups conversations into Pinned, Folders, Date-grouped (ungrouped),
  and Archived sections. Provides context menus, folder management,
  and search/filter. Uses Svelte 5 runes.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, Search, Sparkles, FolderPlus, Archive, Pin, ChevronRight, ChevronDown } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import {
		conversations,
		activeConversationId,
		clearMessages,
		loadConversations,
		loadFolders,
		selectConversation,
		createNewConversation,
		folders
	} from '$lib/stores/chat.js';
	import {
		renameConversation,
		deleteConversation,
		pinConversation,
		archiveConversation,
		moveToFolder,
		createFolder,
		renameFolder as apiFenameFolder,
		deleteFolder as apiDeleteFolder
	} from '$lib/services/conversations.js';
	import ConversationItem from './ConversationItem.svelte';
	import ConversationContextMenu from './ConversationContextMenu.svelte';
	import FolderCreateModal from './FolderCreateModal.svelte';
	import FolderTree from './FolderTree.svelte';

	let searchQuery = $state('');
	let contextMenuId = $state<string | null>(null);
	let contextMenuPos = $state({ x: 0, y: 0 });
	let collapsedSections = $state<Set<string>>(new Set(['archived']));
	let deletingId = $state<string | null>(null);
	let showFolderModal = $state(false);

	// Load data on mount
	$effect(() => {
		loadConversations();
		loadFolders();
	});

	// -----------------------------------------------------------------------
	// Date grouping
	// -----------------------------------------------------------------------

	const DATE_GROUPS = ['Today', 'Yesterday', 'This Week', 'Older'] as const;

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
	// Derived grouping
	// -----------------------------------------------------------------------

	let filtered = $derived(
		$conversations.filter(
			(c) => !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	let pinnedConvos = $derived(
		filtered.filter((c) => c.metadata?.pinned && !c.metadata?.archived)
	);

	let archivedConvos = $derived(
		filtered.filter((c) => c.metadata?.archived)
	);

	let folderGroups = $derived.by(() => {
		const groups: Record<string, typeof $conversations> = {};
		for (const conv of filtered) {
			const fid = conv.metadata?.folder_id as string | undefined;
			if (fid && !conv.metadata?.pinned && !conv.metadata?.archived) {
				if (!groups[fid]) groups[fid] = [];
				groups[fid].push(conv);
			}
		}
		return groups;
	});

	let ungrouped = $derived.by(() => {
		const convos = filtered.filter(
			(c) => !c.metadata?.pinned && !c.metadata?.archived && !c.metadata?.folder_id
		);
		const groups: Record<string, typeof $conversations> = {};
		for (const conv of convos) {
			const group = getDateGroup(conv.updatedAt);
			if (!groups[group]) groups[group] = [];
			groups[group].push(conv);
		}
		return groups;
	});

	let contextConvo = $derived(
		contextMenuId ? $conversations.find((c) => c.id === contextMenuId) : null
	);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function toggleSection(key: string) {
		const next = new Set(collapsedSections);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		collapsedSections = next;
	}

	async function handleNew() {
		await createNewConversation();
	}

	async function handleSelect(id: string) {
		if (contextMenuId || deletingId === id) return;
		await selectConversation(id);
	}

	function openContextMenu(id: string, x: number, y: number) {
		contextMenuId = id;
		contextMenuPos = { x, y };
	}

	function closeContextMenu() {
		contextMenuId = null;
	}

	async function handleRename(id: string, newTitle: string) {
		try {
			await renameConversation(id, newTitle);
			conversations.update((convs) =>
				convs.map((c) => (c.id === id ? { ...c, title: newTitle } : c))
			);
		} catch (error) {
			console.error('[ConversationList] Rename failed:', error);
		}
	}

	async function handlePin() {
		if (!contextMenuId || !contextConvo) return;
		const id = contextMenuId;
		const wasPinned = !!contextConvo.metadata?.pinned;
		try {
			await pinConversation(id, !wasPinned);
			conversations.update((convs) =>
				convs.map((c) =>
					c.id === id ? { ...c, metadata: { ...c.metadata, pinned: !wasPinned } } : c
				)
			);
		} catch (error) {
			console.error('[ConversationList] Pin failed:', error);
		}
	}

	async function handleArchive() {
		if (!contextMenuId || !contextConvo) return;
		const id = contextMenuId;
		const wasArchived = !!contextConvo.metadata?.archived;
		try {
			await archiveConversation(id, !wasArchived);
			conversations.update((convs) =>
				convs.map((c) =>
					c.id === id ? { ...c, metadata: { ...c.metadata, archived: !wasArchived } } : c
				)
			);
		} catch (error) {
			console.error('[ConversationList] Archive failed:', error);
		}
	}

	async function handleMoveToFolder(folderId: string | null) {
		if (!contextMenuId) return;
		const id = contextMenuId;
		try {
			await moveToFolder(id, folderId);
			conversations.update((convs) =>
				convs.map((c) =>
					c.id === id
						? {
								...c,
								metadata: folderId
									? { ...c.metadata, folder_id: folderId }
									: (() => {
											const { folder_id: _, ...rest } = c.metadata;
											return rest;
										})()
							}
						: c
				)
			);
		} catch (error) {
			console.error('[ConversationList] Move failed:', error);
		}
	}

	async function handleNewFolder() {
		showFolderModal = true;
	}

	async function handleCreateFolder(name: string, icon: string) {
		showFolderModal = false;
		try {
			await createFolder(name, icon);
			await loadFolders();
		} catch (error) {
			console.error('[ConversationList] Create folder failed:', error);
		}
	}

	async function handleDelete() {
		if (!contextMenuId) return;
		const id = contextMenuId;
		try {
			await deleteConversation(id);
			conversations.update((convs) => convs.filter((c) => c.id !== id));
			if ($activeConversationId === id) {
				$activeConversationId = null;
				clearMessages();
				goto('/');
			}
		} catch (error) {
			console.error('[ConversationList] Delete failed:', error);
		}
	}

	async function handleFolderRename(folderId: string, name: string) {
		try {
			await apiFenameFolder(folderId, name);
			await loadFolders();
		} catch (error) {
			console.error('[ConversationList] Folder rename failed:', error);
		}
	}

	async function handleFolderDelete(folderId: string) {
		try {
			await apiDeleteFolder(folderId);
			await loadFolders();
			await loadConversations();
		} catch (error) {
			console.error('[ConversationList] Folder delete failed:', error);
		}
	}

	function handleContextRename() {
		// Context menu rename triggers the ConversationItem's inline rename
		// We close the menu and the item will handle it via double-click simulation
		// For simplicity, we trigger a custom approach: find the item and rename directly
		if (!contextMenuId || !contextConvo) return;
		const newTitle = prompt('Rename conversation:', contextConvo.title);
		if (newTitle?.trim()) {
			handleRename(contextMenuId, newTitle.trim());
		}
	}
</script>

<div class="flex h-full flex-col">
	<!-- Header area -->
	<div class="space-y-2.5 px-3 pb-3 pt-3">
		<!-- New Conversation button -->
		<button
			type="button"
			onclick={handleNew}
			class="group/new flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2.5 text-sm font-medium text-white shadow-sm transition-all hover:bg-accent/90 active:scale-[0.98]"
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

		<!-- New Folder button -->
		<button
			type="button"
			onclick={handleNewFolder}
			class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			<FolderPlus size={13} />
			New Folder
		</button>
	</div>

	<!-- Divider -->
	<div class="mx-3 h-px bg-border/30"></div>

	<!-- Conversation items -->
	<div class="flex-1 overflow-y-auto pt-1">
		{#if filtered.length === 0 && $conversations.length === 0}
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
		{:else if filtered.length === 0}
			<!-- No search results -->
			<div class="px-4 py-8 text-center text-xs text-text-secondary">
				No conversations match "{searchQuery}"
			</div>
		{:else}
			<!-- Pinned section -->
			{#if pinnedConvos.length > 0}
				<div class="mb-1">
					<button
						type="button"
						onclick={() => toggleSection('pinned')}
						class="flex w-full items-center gap-1.5 px-4 pb-1 pt-3"
					>
						{#if collapsedSections.has('pinned')}
							<ChevronRight size={12} class="text-text-secondary/50" />
						{:else}
							<ChevronDown size={12} class="text-text-secondary/50" />
						{/if}
						<Pin size={12} class="text-text-secondary/50" />
						<span class="text-[10px] font-semibold uppercase tracking-widest text-text-secondary/50">
							Pinned
						</span>
						<span class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-[9px] font-medium text-text-secondary">
							{pinnedConvos.length}
						</span>
					</button>
					{#if !collapsedSections.has('pinned')}
						{#each pinnedConvos as conversation (conversation.id)}
							<ConversationItem
								id={conversation.id}
								title={conversation.title}
								updatedAt={conversation.updatedAt}
								isActive={$activeConversationId === conversation.id}
								isPinned={true}
								onSelect={handleSelect}
								onContextMenu={openContextMenu}
								onRename={handleRename}
							/>
						{/each}
					{/if}
				</div>
				<div class="mx-3 h-px bg-border/20"></div>
			{/if}

			<!-- Folder sections -->
			{#each $folders as folder (folder.id)}
				{@const folderConvos = folderGroups[folder.id] ?? []}
				{#if folderConvos.length > 0 || !searchQuery}
					<FolderTree
						{folder}
						count={folderConvos.length}
						collapsed={collapsedSections.has(`folder-${folder.id}`)}
						onToggle={() => toggleSection(`folder-${folder.id}`)}
						onRename={handleFolderRename}
						onDelete={handleFolderDelete}
					>
						{#each folderConvos as conversation (conversation.id)}
							<ConversationItem
								id={conversation.id}
								title={conversation.title}
								updatedAt={conversation.updatedAt}
								isActive={$activeConversationId === conversation.id}
								isPinned={false}
								onSelect={handleSelect}
								onContextMenu={openContextMenu}
								onRename={handleRename}
							/>
						{/each}
					</FolderTree>
				{/if}
			{/each}

			{#if $folders.length > 0 && Object.keys(folderGroups).length > 0}
				<div class="mx-3 h-px bg-border/20"></div>
			{/if}

			<!-- Ungrouped conversations by date -->
			{#each DATE_GROUPS as groupName}
				{#if ungrouped[groupName]?.length}
					<div class="px-4 pb-1 pt-3">
						<span class="text-[10px] font-semibold uppercase tracking-widest text-text-secondary/50">
							{groupName}
						</span>
					</div>
					{#each ungrouped[groupName] as conversation (conversation.id)}
						<ConversationItem
							id={conversation.id}
							title={conversation.title}
							updatedAt={conversation.updatedAt}
							isActive={$activeConversationId === conversation.id}
							isPinned={false}
							onSelect={handleSelect}
							onContextMenu={openContextMenu}
							onRename={handleRename}
						/>
					{/each}
				{/if}
			{/each}

			<!-- Archived section (collapsed by default) -->
			{#if archivedConvos.length > 0}
				<div class="mx-3 mt-2 h-px bg-border/20"></div>
				<div class="mb-1">
					<button
						type="button"
						onclick={() => toggleSection('archived')}
						class="flex w-full items-center gap-1.5 px-4 pb-1 pt-3"
					>
						{#if collapsedSections.has('archived')}
							<ChevronRight size={12} class="text-text-secondary/50" />
						{:else}
							<ChevronDown size={12} class="text-text-secondary/50" />
						{/if}
						<Archive size={12} class="text-text-secondary/50" />
						<span class="text-[10px] font-semibold uppercase tracking-widest text-text-secondary/50">
							Archived
						</span>
						<span class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-[9px] font-medium text-text-secondary">
							{archivedConvos.length}
						</span>
					</button>
					{#if !collapsedSections.has('archived')}
						{#each archivedConvos as conversation (conversation.id)}
							<ConversationItem
								id={conversation.id}
								title={conversation.title}
								updatedAt={conversation.updatedAt}
								isActive={$activeConversationId === conversation.id}
								isPinned={false}
								onSelect={handleSelect}
								onContextMenu={openContextMenu}
								onRename={handleRename}
							/>
						{/each}
					{/if}
				</div>
			{/if}
		{/if}
	</div>

	<!-- Context menu -->
	{#if contextMenuId && contextConvo}
		<ConversationContextMenu
			x={contextMenuPos.x}
			y={contextMenuPos.y}
			isPinned={!!contextConvo.metadata?.pinned}
			isArchived={!!contextConvo.metadata?.archived}
			folders={$folders}
			currentFolderId={(contextConvo.metadata?.folder_id as string) ?? null}
			onPin={handlePin}
			onRename={handleContextRename}
			onMoveToFolder={handleMoveToFolder}
			onNewFolder={handleNewFolder}
			onArchive={handleArchive}
			onDelete={handleDelete}
			onClose={closeContextMenu}
		/>
	{/if}

	<FolderCreateModal
		open={showFolderModal}
		onClose={() => (showFolderModal = false)}
		onCreate={handleCreateFolder}
	/>
</div>
