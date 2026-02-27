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
	class="conversation-item group relative mx-1.5 mb-px rounded-lg transition-all duration-200 ease-out
		{isActive
			? 'is-active bg-surface-elevated shadow-[0_1px_3px_rgba(0,0,0,0.06),0_0_0_1px_var(--color-border)/0.3] ring-1 ring-accent/[0.12]'
			: 'hover:bg-surface-hover/50'}"
	draggable={!editing}
	ondragstart={(e) => {
		e.dataTransfer?.setData('text/conversation-id', id);
		e.dataTransfer!.effectAllowed = 'move';
	}}
	oncontextmenu={handleRightClick}
>
	<!-- Active indicator bar -->
	{#if isActive}
		<div class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent shadow-[0_0_6px_var(--color-glow-accent)]"></div>
	{/if}

	<button
		type="button"
		onclick={() => { if (!editing) onSelect(id); }}
		ondblclick={startRename}
		class="flex w-full items-center gap-2.5 px-2.5 py-[9px] text-left"
		disabled={editing}
	>
		<!-- Icon -->
		<span
			class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors duration-200
				{isActive
					? 'bg-accent/[0.08] text-accent'
					: 'text-text-secondary/40 group-hover:text-text-secondary/70'}"
		>
			{#if isPinned}
				<Pin size={14} class="rotate-45" />
			{:else}
				<MessageSquare size={14} />
			{/if}
		</span>

		<!-- Content -->
		<div class="min-w-0 flex-1">
			{#if editing}
				<!-- svelte-ignore a11y_autofocus -->
				<input
					type="text"
					bind:value={editTitle}
					onkeydown={handleKeydown}
					autofocus
					class="w-full rounded-md border border-accent/40 bg-surface px-2 py-1 text-[13px] text-text-primary shadow-inner outline-none transition-shadow focus:border-accent/60 focus:shadow-[0_0_0_3px_var(--color-glow-accent)]"
					onclick={(e) => e.stopPropagation()}
				/>
			{:else}
				<div
					class="truncate text-[13px] leading-snug transition-colors duration-150
						{isActive
							? 'font-semibold text-text-primary'
							: 'font-medium text-text-primary/85 group-hover:text-text-primary'}"
				>
					{title}
				</div>
				<div class="mt-px text-[11px] leading-snug text-text-secondary/45">
					{formatRelativeTime(updatedAt)}
				</div>
			{/if}
		</div>
	</button>

	<!-- Hover actions -->
	{#if editing}
		<div class="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
			<button
				type="button"
				onclick={confirmRename}
				class="flex h-6 w-6 items-center justify-center rounded-md bg-success/10 text-success transition-colors hover:bg-success/20"
				aria-label="Confirm rename"
			>
				<Check size={13} />
			</button>
			<button
				type="button"
				onclick={cancelRename}
				class="flex h-6 w-6 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				aria-label="Cancel rename"
			>
				<X size={13} />
			</button>
		</div>
	{:else}
		<div
			class="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-px rounded-md bg-surface-elevated/90 opacity-0 shadow-sm ring-1 ring-border/20 backdrop-blur-sm transition-all duration-200 group-hover:opacity-100"
		>
			<button
				type="button"
				onclick={startRename}
				class="flex h-6 w-6 items-center justify-center rounded-l-md text-text-secondary/60 transition-colors hover:bg-surface-hover hover:text-text-primary"
				aria-label="Rename conversation"
			>
				<Pencil size={11} />
			</button>
			<button
				type="button"
				onclick={handleDotClick}
				class="flex h-6 w-6 items-center justify-center rounded-r-md text-text-secondary/60 transition-colors hover:bg-surface-hover hover:text-text-primary"
				aria-label="More actions"
			>
				<MoreHorizontal size={13} />
			</button>
		</div>
	{/if}
</div>
