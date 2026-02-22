<!--
  KeyValueList.svelte - Vertical list of key-value pairs.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface KeyValueListProps {
		items: Array<{ key: string; value: string }>;
		title?: string;
	}

	let { items, title }: KeyValueListProps = $props();
</script>

<div class="rounded-lg border border-border bg-surface">
	{#if title}
		<div class="border-b border-border px-4 py-2.5">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<dl class="divide-y divide-border">
		{#each items as item}
			<div class="flex items-baseline justify-between gap-4 px-4 py-2">
				<dt class="shrink-0 text-xs text-text-secondary">{item.key}</dt>
				<dd class="truncate text-right text-sm text-text-primary">{item.value}</dd>
			</div>
		{/each}
	</dl>
</div>
