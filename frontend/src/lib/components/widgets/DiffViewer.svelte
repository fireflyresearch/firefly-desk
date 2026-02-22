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

<div class="rounded-lg border border-border bg-surface">
	{#if title}
		<div class="border-b border-border px-4 py-2.5">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="overflow-x-auto">
		<table class="w-full text-left text-sm">
			<thead>
				<tr class="border-b border-border bg-surface-secondary">
					<th class="px-4 py-2 text-xs font-medium text-text-secondary">Field</th>
					<th class="px-4 py-2 text-xs font-medium text-text-secondary">Before</th>
					<th class="w-6 px-1 py-2"></th>
					<th class="px-4 py-2 text-xs font-medium text-text-secondary">After</th>
				</tr>
			</thead>
			<tbody>
				{#each allKeys as key}
					{@const beforeVal = before[key] ?? ''}
					{@const afterVal = after[key] ?? ''}
					{@const changed = beforeVal !== afterVal}
					<tr class="border-b border-border last:border-b-0">
						<td class="px-4 py-2 text-xs font-medium text-text-secondary">{key}</td>
						<td
							class="px-4 py-2 font-mono text-xs {changed
								? 'bg-danger/5 text-danger'
								: 'text-text-secondary'}"
						>
							{beforeVal || '--'}
						</td>
						<td class="px-1 py-2 text-center text-text-secondary">
							{#if changed}
								<ArrowRight size={12} />
							{/if}
						</td>
						<td
							class="px-4 py-2 font-mono text-xs {changed
								? 'bg-success/5 text-success'
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
