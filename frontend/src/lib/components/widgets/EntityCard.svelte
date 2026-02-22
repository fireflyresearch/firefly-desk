<!--
  EntityCard.svelte - Card showing an entity's details with fields and optional status.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import StatusBadge from './StatusBadge.svelte';

	interface EntityCardProps {
		title: string;
		subtitle?: string;
		fields: Array<{ label: string; value: string }>;
		status?: string;
	}

	let { title, subtitle, fields, status }: EntityCardProps = $props();
</script>

<div class="rounded-lg border border-border bg-surface p-4">
	<!-- Header -->
	<div class="flex items-start justify-between gap-3">
		<div class="min-w-0">
			<h3 class="truncate text-sm font-semibold text-text-primary">{title}</h3>
			{#if subtitle}
				<p class="mt-0.5 truncate text-xs text-text-secondary">{subtitle}</p>
			{/if}
		</div>
		{#if status}
			<div class="shrink-0">
				<StatusBadge label={status} status="neutral" />
			</div>
		{/if}
	</div>

	<!-- Fields -->
	{#if fields.length > 0}
		<div class="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
			{#each fields as field}
				<div class="min-w-0">
					<dt class="text-xs text-text-secondary">{field.label}</dt>
					<dd class="mt-0.5 truncate text-sm text-text-primary">{field.value}</dd>
				</div>
			{/each}
		</div>
	{/if}
</div>
