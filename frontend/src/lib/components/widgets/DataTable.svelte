<!--
  DataTable.svelte - Table displaying tabular data with header and alternating rows.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface DataTableProps {
		columns: Array<{ key: string; label: string }>;
		rows: Array<Record<string, unknown>>;
		title?: string;
	}

	let { columns, rows, title }: DataTableProps = $props();
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm">
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="overflow-x-auto">
		<table class="w-full text-left text-sm">
			<thead>
				<tr class="sticky top-0 z-10 border-b border-border bg-surface-secondary/50">
					{#each columns as column}
						<th class="px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-text-secondary">
							{column.label}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each rows as row, i}
					<tr
						class="border-b border-border last:border-b-0 {i % 2 === 1
							? 'bg-surface-secondary/30'
							: ''}"
					>
						{#each columns as column}
							<td class="px-4 py-2.5 text-text-primary">
								{row[column.key] ?? ''}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
