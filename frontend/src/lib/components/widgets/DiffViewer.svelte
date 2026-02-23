<!--
  DiffViewer.svelte - Shows before/after comparison of field values.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowRight } from 'lucide-svelte';

	interface DiffViewerProps {
		before: Record<string, string>;
		after: Record<string, string>;
		title?: string;
	}

	let { before, after, title }: DiffViewerProps = $props();

	let allKeys = $derived(
		[...new Set([...Object.keys(before), ...Object.keys(after)])].sort()
	);
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm">
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="overflow-x-auto">
		<table class="w-full text-left text-sm font-mono">
			<thead>
				<tr class="sticky top-0 z-10 border-b border-border bg-surface-secondary/50">
					<th class="px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-text-secondary font-sans">Field</th>
					<th class="px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-text-secondary font-sans">Before</th>
					<th class="w-6 px-1 py-2.5"></th>
					<th class="px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-text-secondary font-sans">After</th>
				</tr>
			</thead>
			<tbody>
				{#each allKeys as key}
					{@const beforeVal = before[key] ?? ''}
					{@const afterVal = after[key] ?? ''}
					{@const changed = beforeVal !== afterVal}
					<tr class="border-b border-border last:border-b-0">
						<td class="px-4 py-2.5 text-xs font-medium text-text-secondary font-sans">{key}</td>
						<td
							class="px-4 py-2.5 text-xs {changed
								? 'bg-danger/10 text-danger'
								: 'text-text-secondary'}"
						>
							{beforeVal || '--'}
						</td>
						<td class="px-1 py-2.5 text-center text-text-secondary">
							{#if changed}
								<ArrowRight size={12} />
							{/if}
						</td>
						<td
							class="px-4 py-2.5 text-xs {changed
								? 'bg-success/10 text-success'
								: 'text-text-secondary'}"
						>
							{afterVal || '--'}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
