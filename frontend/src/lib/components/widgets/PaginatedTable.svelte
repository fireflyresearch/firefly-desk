<!--
  PaginatedTable.svelte - Server-side paginated table with filter event support.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { untrack } from 'svelte';

	interface Column {
		key: string;
		label: string;
	}

	interface PaginatedTableProps {
		columns: Column[];
		data_endpoint: string;
		page_size?: number;
		total_count?: number;
		title?: string;
		widget_id?: string;
	}

	let {
		columns,
		data_endpoint,
		page_size = 25,
		total_count = 0,
		title,
		widget_id
	}: PaginatedTableProps = $props();

	let rows: Record<string, unknown>[] = $state([]);
	let offset = $state(0);
	let loading = $state(false);
	let error = $state('');
	let totalRows = $state(untrack(() => total_count));
	let filterParams = $state('');

	let currentPage = $derived(Math.floor(offset / page_size) + 1);
	let totalPages = $derived(Math.max(1, Math.ceil(totalRows / page_size)));
	let hasPrev = $derived(offset > 0);
	let hasNext = $derived(offset + page_size < totalRows);

	$effect(() => {
		fetchPage();
	});

	$effect(() => {
		if (!widget_id) return;
		function handleFilter(e: CustomEvent) {
			if (e.detail?.targetId === widget_id) {
				filterParams = e.detail.queryString || '';
				offset = 0;
				fetchPage();
			}
		}
		window.addEventListener('widget-filter-change', handleFilter as EventListener);
		return () =>
			window.removeEventListener('widget-filter-change', handleFilter as EventListener);
	});

	async function fetchPage() {
		loading = true;
		error = '';
		try {
			const sep = data_endpoint.includes('?') ? '&' : '?';
			const url = `${data_endpoint}${sep}offset=${offset}&limit=${page_size}${filterParams ? '&' + filterParams : ''}`;
			const resp = await fetch(url);
			if (!resp.ok) throw new Error(resp.statusText);
			const body = await resp.json();
			rows = body.rows ?? body.items ?? body.data ?? [];
			if (body.total != null) totalRows = body.total;
			if (body.total_count != null) totalRows = body.total_count;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Fetch failed';
		} finally {
			loading = false;
		}
	}

	function prevPage() {
		offset = Math.max(0, offset - page_size);
		fetchPage();
	}

	function nextPage() {
		offset += page_size;
		fetchPage();
	}
</script>

<div class="overflow-hidden rounded-lg border border-border bg-surface">
	{#if title}
		<div class="border-b border-border px-4 py-2">
			<h4 class="text-sm font-semibold text-text-primary">{title}</h4>
		</div>
	{/if}

	<div class="overflow-auto">
		{#if loading}
			<div class="flex items-center justify-center py-8">
				<div
					class="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent"
				></div>
			</div>
		{:else if error}
			<div class="px-4 py-8 text-center text-sm text-danger">{error}</div>
		{:else}
			<table class="w-full text-left text-xs">
				<thead>
					<tr class="border-b border-border bg-surface-secondary">
						{#each columns as col}
							<th
								class="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-secondary"
							>
								{col.label}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each rows as row, i}
						<tr
							class="border-b border-border/50 {i % 2 === 0
								? ''
								: 'bg-surface-secondary/50'}"
						>
							{#each columns as col}
								<td class="px-3 py-1.5 text-text-primary">{row[col.key] ?? ''}</td>
							{/each}
						</tr>
					{/each}
					{#if rows.length === 0}
						<tr>
							<td
								colspan={columns.length}
								class="px-4 py-8 text-center text-sm text-text-secondary"
							>
								No data
							</td>
						</tr>
					{/if}
				</tbody>
			</table>
		{/if}
	</div>

	<!-- Pagination controls -->
	<div class="flex items-center justify-between border-t border-border px-4 py-2">
		<span class="text-xs text-text-secondary">
			{totalRows > 0
				? `${offset + 1}\u2013${Math.min(offset + page_size, totalRows)} of ${totalRows}`
				: 'No results'}
		</span>
		<div class="flex items-center gap-2">
			<button
				type="button"
				class="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-secondary disabled:opacity-30"
				disabled={!hasPrev}
				onclick={prevPage}
			>
				Previous
			</button>
			<span class="text-xs text-text-secondary">Page {currentPage} of {totalPages}</span>
			<button
				type="button"
				class="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-secondary disabled:opacity-30"
				disabled={!hasNext}
				onclick={nextPage}
			>
				Next
			</button>
		</div>
	</div>
</div>
