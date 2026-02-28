<!--
  KGToolbar.svelte - Top toolbar for the Knowledge Graph Explorer.

  Provides refresh, filter toggle, and regenerate controls.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, RefreshCw, PanelLeftClose, PanelLeft, Sparkles, Box, LayoutGrid } from 'lucide-svelte';

	interface Props {
		showFilterPanel: boolean;
		regenerating: boolean;
		regenerateMessage: string;
		regenerateProgress: number;
		viewMode: '2d' | '3d';
		webglAvailable: boolean;
		onToggleFilter: () => void;
		onRefresh: () => void;
		onRegenerate?: () => void;
		onToggleViewMode: () => void;
	}

	let {
		showFilterPanel,
		regenerating,
		regenerateMessage,
		regenerateProgress,
		viewMode,
		webglAvailable,
		onToggleFilter,
		onRefresh,
		onRegenerate,
		onToggleViewMode
	}: Props = $props();
</script>

<div class="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
	<button
		type="button"
		onclick={onToggleFilter}
		class="inline-flex shrink-0 items-center rounded-md border border-border p-1.5 text-text-secondary transition-colors hover:bg-surface-hover"
		title="{showFilterPanel ? 'Hide' : 'Show'} filter panel"
	>
		{#if showFilterPanel}
			<PanelLeftClose size={14} />
		{:else}
			<PanelLeft size={14} />
		{/if}
	</button>

	<button
		type="button"
		onclick={onRefresh}
		class="inline-flex shrink-0 items-center rounded-md border border-border p-1.5 text-text-secondary transition-colors hover:bg-surface-hover"
		title="Refresh graph data"
	>
		<RefreshCw size={14} />
	</button>

	{#if webglAvailable}
		<button
			type="button"
			onclick={onToggleViewMode}
			class="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
			title="Switch to {viewMode === '3d' ? '2D' : '3D'} view"
		>
			{#if viewMode === '3d'}
				<LayoutGrid size={13} />
				2D
			{:else}
				<Box size={13} />
				3D
			{/if}
		</button>
	{/if}

	<div class="flex-1"></div>

	{#if regenerateMessage}
		<span class="text-xs text-text-secondary">{regenerateMessage}</span>
	{/if}

	{#if onRegenerate}
		<button
			type="button"
			onclick={onRegenerate}
			disabled={regenerating}
			class="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
		>
			{#if regenerating}
				<Loader2 size={13} class="animate-spin" />
				Regenerating...
			{:else}
				<Sparkles size={13} />
				Regenerate
			{/if}
		</button>
	{/if}
</div>

{#if regenerating}
	<div class="h-1 w-full shrink-0 overflow-hidden bg-surface-secondary">
		<div
			class="h-full rounded-full bg-accent transition-all duration-500"
			style="width: {regenerateProgress}%"
		></div>
	</div>
{/if}
