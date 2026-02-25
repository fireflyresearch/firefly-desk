<!--
  DynamicFilter.svelte - Standalone filter widget dispatching filter events to target widgets.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Search } from 'lucide-svelte';

	interface FilterField {
		field: string;
		label: string;
		type: 'text' | 'date_range' | 'select' | 'number_range';
		options?: string[];
	}

	interface DynamicFilterProps {
		filters: FilterField[];
		target_widget_id?: string;
		title?: string;
	}

	let { filters, target_widget_id, title }: DynamicFilterProps = $props();

	type RangeValue = { from?: string; to?: string; min?: string; max?: string };
	let textValues: Record<string, string> = $state({});
	let rangeValues: Record<string, RangeValue> = $state({});

	function getRange(field: string): RangeValue {
		return rangeValues[field] ?? {};
	}

	function setRange(field: string, patch: Partial<RangeValue>) {
		rangeValues[field] = { ...getRange(field), ...patch };
		dispatchFilter();
	}

	function dispatchFilter() {
		const params = new URLSearchParams();
		for (const f of filters) {
			if (f.type === 'date_range' || f.type === 'number_range') {
				const rv = getRange(f.field);
				if (f.type === 'date_range') {
					if (rv.from) params.set(`${f.field}_from`, rv.from);
					if (rv.to) params.set(`${f.field}_to`, rv.to);
				} else {
					if (rv.min != null && rv.min !== '') params.set(`${f.field}_min`, rv.min);
					if (rv.max != null && rv.max !== '') params.set(`${f.field}_max`, rv.max);
				}
			} else {
				const val = textValues[f.field];
				if (val != null && val !== '') params.set(f.field, val);
			}
		}
		window.dispatchEvent(
			new CustomEvent('widget-filter-change', {
				detail: { targetId: target_widget_id, queryString: params.toString() }
			})
		);
	}

	function clearAll() {
		textValues = {};
		rangeValues = {};
		dispatchFilter();
	}

	let hasValues = $derived(
		Object.values(textValues).some((v) => v != null && v !== '') ||
			Object.values(rangeValues).some((rv) =>
				Object.values(rv).some((sv) => sv != null && sv !== '')
			)
	);
</script>

<div class="rounded-lg border border-border bg-surface p-3">
	{#if title}
		<h4 class="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
			{title}
		</h4>
	{/if}

	<div class="flex flex-wrap items-end gap-3">
		{#each filters as f}
			<div class="flex flex-col gap-1">
				<label class="text-xs text-text-secondary" for="filter-{f.field}">{f.label}</label>

				{#if f.type === 'text'}
					<div class="relative">
						<Search
							size={12}
							class="absolute left-2 top-1/2 -translate-y-1/2 text-text-secondary"
						/>
						<input
							id="filter-{f.field}"
							type="text"
							class="w-40 rounded border border-border bg-surface-secondary py-1 pl-7 pr-2 text-xs text-text-primary outline-none focus:border-accent"
							bind:value={textValues[f.field]}
							oninput={dispatchFilter}
							placeholder="Search..."
						/>
					</div>
				{:else if f.type === 'select' && f.options}
					<select
						id="filter-{f.field}"
						class="w-36 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
						bind:value={textValues[f.field]}
						onchange={dispatchFilter}
					>
						<option value="">All</option>
						{#each f.options as opt}
							<option value={opt}>{opt}</option>
						{/each}
					</select>
				{:else if f.type === 'date_range'}
					<div class="flex items-center gap-1">
						<input
							type="date"
							class="w-32 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							value={getRange(f.field).from ?? ''}
							oninput={(e) => setRange(f.field, { from: e.currentTarget.value })}
						/>
						<span class="text-xs text-text-secondary">&ndash;</span>
						<input
							type="date"
							class="w-32 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							value={getRange(f.field).to ?? ''}
							oninput={(e) => setRange(f.field, { to: e.currentTarget.value })}
						/>
					</div>
				{:else if f.type === 'number_range'}
					<div class="flex items-center gap-1">
						<input
							type="number"
							class="w-20 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							placeholder="Min"
							value={getRange(f.field).min ?? ''}
							oninput={(e) => setRange(f.field, { min: e.currentTarget.value })}
						/>
						<span class="text-xs text-text-secondary">&ndash;</span>
						<input
							type="number"
							class="w-20 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							placeholder="Max"
							value={getRange(f.field).max ?? ''}
							oninput={(e) => setRange(f.field, { max: e.currentTarget.value })}
						/>
					</div>
				{/if}
			</div>
		{/each}

		{#if hasValues}
			<button
				type="button"
				class="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-secondary hover:text-text-primary"
				onclick={clearAll}
			>
				Clear
			</button>
		{/if}
	</div>
</div>
