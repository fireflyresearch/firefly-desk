<!--
  FolderTree.svelte - Collapsible folder sections in the sidebar.

  Renders folder headers with chevron, name, conversation count badge,
  and inline rename/delete. Hosts ConversationItem children per folder.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Folder,
		ChevronRight,
		ChevronDown,
		MoreHorizontal,
		Pencil,
		Trash2,
		Check,
		X,
		Star,
		Heart,
		Briefcase,
		Code,
		BookOpen,
		Lightbulb,
		Zap,
		Globe,
		Shield,
		Coffee,
		Flame,
		Music,
		Camera,
		Palette,
		Rocket,
		Target,
		Award,
		Gift,
		MessageCircle,
		Bell,
		Hash,
		Bookmark,
		Archive
	} from 'lucide-svelte';
	import type { ApiFolder } from '$lib/services/conversations.js';
	import type { Snippet } from 'svelte';

	const iconMap: Record<string, typeof Folder> = {
		folder: Folder,
		star: Star,
		heart: Heart,
		briefcase: Briefcase,
		code: Code,
		book: BookOpen,
		lightbulb: Lightbulb,
		zap: Zap,
		globe: Globe,
		shield: Shield,
		coffee: Coffee,
		flame: Flame,
		music: Music,
		camera: Camera,
		palette: Palette,
		rocket: Rocket,
		target: Target,
		award: Award,
		gift: Gift,
		message: MessageCircle,
		bell: Bell,
		hash: Hash,
		bookmark: Bookmark,
		archive: Archive
	};

	interface FolderTreeProps {
		folder: ApiFolder;
		count: number;
		collapsed: boolean;
		onToggle: () => void;
		onRename: (id: string, name: string) => void;
		onDelete: (id: string) => void;
		onDrop: (conversationId: string, folderId: string) => void;
		children: Snippet;
	}

	let {
		folder,
		count,
		collapsed,
		onToggle,
		onRename,
		onDelete,
		onDrop,
		children
	}: FolderTreeProps = $props();

	let editing = $state(false);
	let editName = $state('');
	let showActions = $state(false);
	let dragOver = $state(false);

	function startRename() {
		editing = true;
		editName = folder.name;
		showActions = false;
	}

	function confirmRename() {
		const trimmed = editName.trim();
		if (trimmed && trimmed !== folder.name) {
			onRename(folder.id, trimmed);
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
</script>

<div class="mb-1">
	<!-- Folder header -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="group flex items-center gap-1 px-3 py-1.5 rounded-md transition-colors
			{dragOver ? 'bg-accent/10 ring-1 ring-accent/30' : ''}"
		ondragover={(e) => {
			if (e.dataTransfer?.types.includes('text/conversation-id')) {
				e.preventDefault();
				e.dataTransfer!.dropEffect = 'move';
				dragOver = true;
			}
		}}
		ondragleave={() => { dragOver = false; }}
		ondrop={(e) => {
			e.preventDefault();
			dragOver = false;
			const convId = e.dataTransfer?.getData('text/conversation-id');
			if (convId) onDrop(convId, folder.id);
		}}
	>
		<button
			type="button"
			onclick={onToggle}
			class="flex items-center gap-1.5 text-text-secondary/60 hover:text-text-primary"
		>
			{#if collapsed}
				<ChevronRight size={12} />
			{:else}
				<ChevronDown size={12} />
			{/if}
			{#if iconMap[folder.icon]}
				<svelte:component this={iconMap[folder.icon]} size={13} />
			{:else}
				<Folder size={13} />
			{/if}
		</button>

		{#if editing}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				type="text"
				bind:value={editName}
				onkeydown={handleKeydown}
				autofocus
				class="flex-1 rounded border border-accent/50 bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-accent"
			/>
			<button
				type="button"
				onclick={confirmRename}
				class="flex h-5 w-5 items-center justify-center rounded text-green-500 hover:bg-green-500/10"
				aria-label="Confirm rename"
			>
				<Check size={11} />
			</button>
			<button
				type="button"
				onclick={cancelRename}
				class="flex h-5 w-5 items-center justify-center rounded text-text-secondary hover:bg-surface-hover"
				aria-label="Cancel rename"
			>
				<X size={11} />
			</button>
		{:else}
			<button
				type="button"
				onclick={onToggle}
				class="flex flex-1 items-center gap-1.5 text-left"
			>
				<span class="text-[11px] font-semibold uppercase tracking-wider text-text-secondary/50">
					{folder.name}
				</span>
				{#if count > 0}
					<span class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-[9px] font-medium text-text-secondary">
						{count}
					</span>
				{/if}
			</button>

			<!-- Folder actions on hover -->
			<div class="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
				<button
					type="button"
					onclick={startRename}
					class="flex h-5 w-5 items-center justify-center rounded text-text-secondary/50 hover:text-text-primary"
					aria-label="Rename folder"
				>
					<Pencil size={10} />
				</button>
				<button
					type="button"
					onclick={() => onDelete(folder.id)}
					class="flex h-5 w-5 items-center justify-center rounded text-text-secondary/50 hover:text-danger"
					aria-label="Delete folder"
				>
					<Trash2 size={10} />
				</button>
			</div>
		{/if}
	</div>

	<!-- Folder contents -->
	{#if !collapsed}
		<div class="ml-2">
			{@render children()}
		</div>
	{/if}
</div>
