<!--
  KGFilterSidebar.svelte - Entity type filter sidebar for the Knowledge Graph Explorer.

  Displays type counts with colored dots, supports show/hide/toggle per type,
  search filter, and stats footer. Slides in/out on toggle.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Filter } from 'lucide-svelte';

	interface Stats {
		entity_count: number;
		relation_count: number;
	}

	interface Props {
		typeCounts: [string, number][];
		hiddenTypes: Set<string>;
		stats: Stats | null;
		filteredEntityCount: number;
		typeColors: Record<string, string>;
		onToggleType: (type: string) => void;
		onShowAll: () => void;
		onHideAll: () => void;
		onShowOnly: (type: string) => void;
	}

	let {
		typeCounts,
		hiddenTypes,
		stats,
		filteredEntityCount,
		typeColors,
		onToggleType,
		onShowAll,
		onHideAll,
		onShowOnly
	}: Props = $props();

	let filterSearch = $state('');

	let visibleTypeCount = $derived(typeCounts.length - hiddenTypes.size);

	let filteredTypeCounts = $derived.by(() => {
		if (!filterSearch.trim()) return typeCounts;
		const q = filterSearch.toLowerCase();
		return typeCounts.filter(([type]) => type.includes(q));
	});

	function getTypeColor(type: string): string {
		return typeColors[type.toLowerCase()] ?? typeColors.default ?? '#6b7280';
	}
</script>

<div class="flex w-52 shrink-0 flex-col border-r border-border bg-surface-secondary/50">
	<!-- Header -->
	<div class="flex items-center justify-between border-b border-border px-3 py-2">
		<div class="flex items-center gap-1.5">
			<Filter size={12} class="text-text-secondary" />
			<span class="text-xs font-semibold text-text-secondary">Entity Types</span>
		</div>
		<span class="rounded-full bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
			{visibleTypeCount}/{typeCounts.length}
		</span>
	</div>

	<!-- Quick actions -->
	<div class="flex gap-1 border-b border-border px-3 py-1.5">
		<button
			type="button"
			onclick={onShowAll}
			class="rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors
				{hiddenTypes.size === 0 ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:bg-surface-hover'}"
		>
			Show All
		</button>
		<button
			type="button"
			onclick={onHideAll}
			class="rounded px-1.5 py-0.5 text-[10px] font-medium text-text-secondary transition-colors hover:bg-surface-hover"
		>
			Hide All
		</button>
	</div>

	<!-- Type search -->
	<div class="border-b border-border px-3 py-1.5">
		<input
			type="text"
			bind:value={filterSearch}
			placeholder="Filter types..."
			class="w-full rounded border border-border bg-surface px-2 py-1 text-[11px] text-text-primary outline-none focus:border-accent"
		/>
	</div>

	<!-- Type list -->
	<div class="flex-1 overflow-y-auto">
		{#each filteredTypeCounts as [type, count]}
			<button
				type="button"
				onclick={() => onToggleType(type)}
				ondblclick={() => onShowOnly(type)}
				class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-surface-hover
					{hiddenTypes.has(type) ? 'opacity-40' : ''}"
				title="Click to toggle, double-click to show only this type"
			>
				<span
					class="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
					style="background-color: {getTypeColor(type)}"
				></span>
				<span class="min-w-0 flex-1 truncate text-[11px] capitalize text-text-primary">
					{type.replace(/_/g, ' ')}
				</span>
				<span class="shrink-0 text-[10px] tabular-nums text-text-secondary">
					{count}
				</span>
			</button>
		{/each}
	</div>

	<!-- Stats footer -->
	{#if stats}
		<div class="border-t border-border px-3 py-2">
			<div class="flex justify-between text-[10px]">
				<span class="text-text-secondary">Entities</span>
				<span class="font-semibold text-text-primary">{stats.entity_count.toLocaleString()}</span>
			</div>
			<div class="flex justify-between text-[10px]">
				<span class="text-text-secondary">Relations</span>
				<span class="font-semibold text-text-primary">{stats.relation_count.toLocaleString()}</span>
			</div>
			<div class="flex justify-between text-[10px]">
				<span class="text-text-secondary">Showing</span>
				<span class="font-semibold text-text-primary">{filteredEntityCount.toLocaleString()}</span>
			</div>
		</div>
	{/if}
</div>
