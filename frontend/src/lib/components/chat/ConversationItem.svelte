<!--
  ConversationItem.svelte - Single conversation row in the sidebar.

  Shows chat icon + title (truncated), three-dot menu on hover,
  inline rename mode, and pin indicator. Uses Svelte 5 runes.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { MessageSquare, MoreHorizontal, Pin, Check, X, Pencil } from 'lucide-svelte';

	interface ConversationItemProps {
		id: string;
		title: string;
		updatedAt: Date;
		isActive: boolean;
		isPinned: boolean;
		onSelect: (id: string) => void;
		onContextMenu: (id: string, x: number, y: number) => void;
		onRename: (id: string, newTitle: string) => void;
	}

	let {
		id,
		title,
		updatedAt,
		isActive,
		isPinned,
		onSelect,
		onContextMenu,
		onRename
	}: ConversationItemProps = $props();

	let editing = $state(false);
	let editTitle = $state('');

	function startRename() {
		editing = true;
		editTitle = title;
	}

	function confirmRename() {
		const trimmed = editTitle.trim();
		if (trimmed && trimmed !== title) {
			onRename(id, trimmed);
		}
		editing = false;
	}

	function cancelRename() {
		editing = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') confirmRename();
		else if (e.key === 'Escape') cancelRename();
	}

	function handleDotClick(e: MouseEvent) {
		e.stopPropagation();
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		onContextMenu(id, rect.right, rect.bottom);
	}

	function handleRightClick(e: MouseEvent) {
		e.preventDefault();
		onContextMenu(id, e.clientX, e.clientY);
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

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="group relative mx-2 mb-0.5 rounded-lg transition-all duration-150
		{isActive ? 'border-l-2 border-accent bg-accent/6' : 'border-l-2 border-transparent hover:bg-surface-hover/60'}"
	oncontextmenu={handleRightClick}
>
	<button
		type="button"
		onclick={() => { if (!editing) onSelect(id); }}
		ondblclick={startRename}
		class="flex w-full items-start gap-2.5 px-3 py-2.5 text-left"
		disabled={editing}
	>
		<span class="mt-0.5 shrink-0 {isActive ? 'text-accent' : 'text-text-secondary/60'}">
			{#if isPinned}
				<Pin size={14} />
			{:else}
				<MessageSquare size={14} />
			{/if}
		</span>
		<div class="min-w-0 flex-1">
			{#if editing}
				<!-- svelte-ignore a11y_autofocus -->
				<input
					type="text"
					bind:value={editTitle}
					onkeydown={handleKeydown}
					autofocus
					class="w-full rounded border border-accent/50 bg-surface px-1.5 py-0.5 text-sm text-text-primary outline-none focus:border-accent"
					onclick={(e) => e.stopPropagation()}
				/>
			{:else}
				<div
					class="line-clamp-1 text-[13px] leading-snug {isActive ? 'font-semibold text-text-primary' : 'font-medium text-text-primary'}"
				>
					{title}
				</div>
			{/if}
			<div class="mt-0.5 text-[11px] text-text-secondary/60 {!isActive ? 'opacity-0 group-hover:opacity-100 transition-opacity' : ''}">
				{formatRelativeTime(updatedAt)}
			</div>
		</div>
	</button>

	<!-- Hover actions -->
	{#if editing}
		<div class="absolute right-2 top-2 flex items-center gap-0.5">
			<button
				type="button"
				onclick={confirmRename}
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
	{:else}
		<div class="absolute right-1.5 top-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
			<button
				type="button"
				onclick={startRename}
				class="flex h-6 w-6 items-center justify-center rounded-md text-text-secondary/70 hover:bg-surface-hover hover:text-text-primary"
				aria-label="Rename conversation"
			>
				<Pencil size={12} />
			</button>
			<button
				type="button"
				onclick={handleDotClick}
				class="flex h-6 w-6 items-center justify-center rounded-md text-text-secondary/70 hover:bg-surface-hover hover:text-text-primary"
				aria-label="More actions"
			>
				<MoreHorizontal size={14} />
			</button>
		</div>
	{/if}
</div>
