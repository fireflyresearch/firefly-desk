<!--
  ConversationContextMenu.svelte - Context menu for conversation actions.

  Provides Pin/Unpin, Rename, Move to Folder, Archive, and Delete actions.
  Positioned relative to trigger point, closes on outside click or Escape.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Pin, Pencil, FolderInput, Archive, Trash2, FolderPlus } from 'lucide-svelte';
	import type { ApiFolder } from '$lib/services/conversations.js';

	interface ContextMenuProps {
		x: number;
		y: number;
		isPinned: boolean;
		isArchived: boolean;
		folders: ApiFolder[];
		currentFolderId: string | null;
		onPin: () => void;
		onRename: () => void;
		onMoveToFolder: (folderId: string | null) => void;
		onNewFolder: () => void;
		onArchive: () => void;
		onDelete: () => void;
		onClose: () => void;
	}

	let {
		x,
		y,
		isPinned,
		isArchived,
		folders,
		currentFolderId,
		onPin,
		onRename,
		onMoveToFolder,
		onNewFolder,
		onArchive,
		onDelete,
		onClose
	}: ContextMenuProps = $props();

	let showFolderSubmenu = $state(false);
	let menuEl: HTMLDivElement | undefined = $state();

	// Clamp position to viewport
	let menuStyle = $derived.by(() => {
		const menuWidth = 200;
		const menuHeight = 280;
		const clampedX = Math.min(x, window.innerWidth - menuWidth - 8);
		const clampedY = Math.min(y, window.innerHeight - menuHeight - 8);
		return `left: ${clampedX}px; top: ${clampedY}px;`;
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}

	function handleAction(action: () => void) {
		action();
		onClose();
	}
</script>

<!-- Backdrop -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-[100]"
	onclick={onClose}
	onkeydown={handleKeydown}
></div>

<!-- Menu -->
<div
	bind:this={menuEl}
	class="fixed z-[101] w-52 overflow-hidden rounded-xl border border-border bg-surface shadow-xl"
	style={menuStyle}
	role="menu"
>
	<!-- Pin/Unpin -->
	<button
		type="button"
		onclick={() => handleAction(onPin)}
		class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover"
		role="menuitem"
	>
		<Pin size={14} class="text-text-secondary" />
		{isPinned ? 'Unpin' : 'Pin'}
	</button>

	<!-- Rename -->
	<button
		type="button"
		onclick={() => handleAction(onRename)}
		class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover"
		role="menuitem"
	>
		<Pencil size={14} class="text-text-secondary" />
		Rename
	</button>

	<!-- Move to Folder -->
	<div class="relative">
		<button
			type="button"
			onclick={() => { showFolderSubmenu = !showFolderSubmenu; }}
			class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover"
			role="menuitem"
		>
			<FolderInput size={14} class="text-text-secondary" />
			Move to Folder
		</button>

		{#if showFolderSubmenu}
			<div class="mx-1 mb-1 overflow-hidden rounded-lg border border-border/50 bg-surface-elevated">
				{#if currentFolderId}
					<button
						type="button"
						onclick={() => handleAction(() => onMoveToFolder(null))}
						class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Remove from folder
					</button>
				{/if}
				{#each folders as folder (folder.id)}
					<button
						type="button"
						onclick={() => handleAction(() => onMoveToFolder(folder.id))}
						class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors hover:bg-surface-hover
							{folder.id === currentFolderId ? 'text-accent font-medium' : 'text-text-primary'}"
					>
						{folder.name}
					</button>
				{/each}
				<button
					type="button"
					onclick={() => handleAction(onNewFolder)}
					class="flex w-full items-center gap-2 border-t border-border/30 px-3 py-1.5 text-left text-xs text-accent transition-colors hover:bg-surface-hover"
				>
					<FolderPlus size={12} />
					New Folder
				</button>
			</div>
		{/if}
	</div>

	<div class="mx-2 h-px bg-border/30"></div>

	<!-- Archive -->
	<button
		type="button"
		onclick={() => handleAction(onArchive)}
		class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover"
		role="menuitem"
	>
		<Archive size={14} class="text-text-secondary" />
		{isArchived ? 'Unarchive' : 'Archive'}
	</button>

	<!-- Delete -->
	<button
		type="button"
		onclick={() => handleAction(onDelete)}
		class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-danger transition-colors hover:bg-danger/10"
		role="menuitem"
	>
		<Trash2 size={14} />
		Delete
	</button>
</div>
