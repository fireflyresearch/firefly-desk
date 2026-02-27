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
	let showDeleteConfirm = $state(false);
	let pendingDeleteId = $state<string | null>(null);
	let showFolderModal = $state(false);
	let folderError = $state<string | null>(null);
	let searchFocused = $state(false);

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
		const newId = await createNewConversation();
		goto(`/chat/${newId}`);
	}

	async function handleSelect(id: string) {
		if (contextMenuId || deletingId === id) return;
		await selectConversation(id);
		goto(`/chat/${id}`);
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
		folderError = null;
		showFolderModal = true;
	}

	async function handleCreateFolder(name: string, icon: string) {
		try {
			await createFolder(name, icon);
			await loadFolders();
			showFolderModal = false;
			folderError = null;
		} catch (err) {
			console.error('[ConversationList] Create folder failed:', err);
			let message = 'Failed to create folder.';
			if (err instanceof Error) {
				// apiFetch throws "API {status} {statusText}: {body}" — extract the body
				const jsonMatch = err.message.match(/:\s*(\{.*\})\s*$/);
				if (jsonMatch) {
					try {
						const body = JSON.parse(jsonMatch[1]);
						message = body.detail ?? body.message ?? err.message;
					} catch {
						message = err.message;
					}
				} else {
					message = err.message;
				}
			}
			folderError = message;
		}
	}

	function requestDelete() {
		if (!contextMenuId) return;
		pendingDeleteId = contextMenuId;
		showDeleteConfirm = true;
	}

	async function confirmDelete() {
		if (!pendingDeleteId) return;
		const id = pendingDeleteId;
		const wasActive = $activeConversationId === id;
		showDeleteConfirm = false;
		pendingDeleteId = null;
		try {
			await deleteConversation(id);
			conversations.update((convs) => convs.filter((c) => c.id !== id));
			if (wasActive) {
				clearMessages();
				await goto('/');
				$activeConversationId = null;
			}
		} catch (error) {
			console.error('[ConversationList] Delete failed:', error);
		}
	}

	function cancelDelete() {
		showDeleteConfirm = false;
		pendingDeleteId = null;
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
	<div class="px-2 pb-2 pt-1.5">
		<!-- Top row: search + action buttons -->
		<div class="flex items-center gap-1.5">
			<div
				class="relative flex-1 transition-all duration-200"
			>
				<Search
					size={13}
					class="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 transition-colors duration-150
						{searchFocused ? 'text-accent' : 'text-text-secondary/50'}"
				/>
				<input
					type="text"
					bind:value={searchQuery}
					onfocus={() => { searchFocused = true; }}
					onblur={() => { searchFocused = false; }}
					placeholder="Search conversations..."
					class="w-full rounded-lg border py-1.5 pl-7 pr-2 text-[12.5px] text-text-primary placeholder:text-text-secondary/40 outline-none transition-all duration-150
						{searchFocused
							? 'border-accent/40 bg-surface ring-1 ring-accent/20'
							: 'border-border/40 bg-surface-secondary/40 hover:border-border/60'}"
				/>
			</div>

			<!-- New Folder button (icon only) -->
			<button
				type="button"
				onclick={handleNewFolder}
				class="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-lg text-text-secondary/50 transition-all duration-150 hover:bg-surface-hover/60 hover:text-text-primary"
				aria-label="New folder"
				title="New folder"
			>
				<FolderPlus size={14} />
			</button>

			<!-- New Conversation button (compact icon) -->
			<button
				type="button"
				onclick={handleNew}
				class="group/new flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-lg bg-accent/[0.08] text-accent transition-all duration-150 hover:bg-accent/[0.15] active:scale-95"
				aria-label="New conversation"
				title="New conversation"
			>
				<Plus size={15} strokeWidth={2.5} class="transition-transform duration-200 group-hover/new:rotate-90" />
			</button>
		</div>
	</div>

	<!-- Conversation items -->
	<div class="flex-1 overflow-y-auto px-0.5 pb-2">
		{#if filtered.length === 0 && $conversations.length === 0}
			<!-- Empty state -->
			<div class="flex flex-col items-center gap-2.5 px-6 py-14 text-center">
				<Sparkles size={16} class="text-text-secondary/30" />
				<p class="text-[12.5px] text-text-secondary/50">
					Ask Ember to start a conversation
				</p>
			</div>
		{:else if filtered.length === 0}
			<!-- No search results -->
			<div class="flex flex-col items-center gap-2 px-6 py-12 text-center">
				<Search size={16} class="text-text-secondary/30" />
				<p class="text-[12px] text-text-secondary/60">
					No results for "{searchQuery}"
				</p>
			</div>
		{:else}
			<!-- Pinned section -->
			{#if pinnedConvos.length > 0}
				<div class="mb-0.5">
					<button
						type="button"
						onclick={() => toggleSection('pinned')}
						class="group/section flex w-full items-center gap-1.5 px-3 pb-1 pt-3 transition-colors"
					>
						<span class="flex h-4 w-4 items-center justify-center text-text-secondary/40 transition-colors group-hover/section:text-text-secondary/60">
							{#if collapsedSections.has('pinned')}
								<ChevronRight size={11} />
							{:else}
								<ChevronDown size={11} />
							{/if}
						</span>
						<Pin size={10} class="text-text-secondary/35" />
						<span class="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-text-secondary/40">
							Pinned
						</span>
						<span class="ml-auto rounded-full bg-surface-hover/60 px-1.5 py-px text-[9px] font-medium tabular-nums text-text-secondary/50">
							{pinnedConvos.length}
						</span>
					</button>
					{#if !collapsedSections.has('pinned')}
						<div class="space-y-px">
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
						</div>
					{/if}
				</div>
				<div class="mx-3 my-1.5 h-px bg-border/15"></div>
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
				<div class="mx-3 my-1.5 h-px bg-border/15"></div>
			{/if}

			<!-- Ungrouped conversations by date -->
			{#each DATE_GROUPS as groupName}
				{#if ungrouped[groupName]?.length}
					<div class="flex items-center gap-2 px-3 pb-1 pt-3">
						<span class="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-text-secondary/40">
							{groupName}
						</span>
						<div class="h-px flex-1 bg-border/10"></div>
					</div>
					<div class="space-y-px">
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
					</div>
				{/if}
			{/each}

			<!-- Archived section (collapsed by default) -->
			{#if archivedConvos.length > 0}
				<div class="mx-3 mt-3 mb-1.5 h-px bg-border/15"></div>
				<div class="mb-1">
					<button
						type="button"
						onclick={() => toggleSection('archived')}
						class="group/section flex w-full items-center gap-1.5 px-3 pb-1 pt-2 transition-colors"
					>
						<span class="flex h-4 w-4 items-center justify-center text-text-secondary/40 transition-colors group-hover/section:text-text-secondary/60">
							{#if collapsedSections.has('archived')}
								<ChevronRight size={11} />
							{:else}
								<ChevronDown size={11} />
							{/if}
						</span>
						<Archive size={10} class="text-text-secondary/35" />
						<span class="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-text-secondary/40">
							Archived
						</span>
						<span class="ml-auto rounded-full bg-surface-hover/60 px-1.5 py-px text-[9px] font-medium tabular-nums text-text-secondary/50">
							{archivedConvos.length}
						</span>
					</button>
					{#if !collapsedSections.has('archived')}
						<div class="space-y-px">
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
						</div>
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
			onDelete={requestDelete}
			onClose={closeContextMenu}
		/>
	{/if}

	{#if showDeleteConfirm}
		<div
			role="dialog"
			aria-modal="true"
			tabindex="-1"
			aria-labelledby="delete-dialog-title"
			aria-describedby="delete-dialog-desc"
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
			onkeydown={(e) => { if (e.key === 'Escape') cancelDelete(); }}
		>
			<div class="w-full max-w-sm rounded-xl border border-border bg-surface-elevated p-5 shadow-xl">
				<h3 id="delete-dialog-title" class="text-sm font-semibold text-text-primary">Delete Conversation</h3>
				<p id="delete-dialog-desc" class="mt-2 text-[13px] text-text-secondary">
					This conversation will be removed from your list.
					Audit history and usage data will be preserved.
				</p>
				<div class="mt-4 flex justify-end gap-2">
					<button
						type="button"
						onclick={cancelDelete}
						class="btn-hover rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-all hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="button"
						onclick={confirmDelete}
						class="btn-hover rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-white transition-all hover:bg-danger/90"
					>
						Delete
					</button>
				</div>
			</div>
		</div>
	{/if}

	<FolderCreateModal
		open={showFolderModal}
		onClose={() => { showFolderModal = false; folderError = null; }}
		onCreate={handleCreateFolder}
		error={folderError}
	/>
</div>
