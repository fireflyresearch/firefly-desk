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

	/** Map common status strings to badge variants */
	function statusVariant(s: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
		const lower = s.toLowerCase();
		if (['active', 'enabled', 'healthy', 'running', 'ok', 'online'].includes(lower)) return 'success';
		if (['warning', 'degraded', 'pending', 'starting'].includes(lower)) return 'warning';
		if (['error', 'failed', 'critical', 'offline', 'down'].includes(lower)) return 'error';
		if (['info', 'new', 'scheduled'].includes(lower)) return 'info';
		return 'neutral';
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm transition-shadow hover:shadow-md">
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
				<StatusBadge label={status} status={statusVariant(status)} />
			</div>
		{/if}
	</div>

	<!-- Fields: two-column grid -->
	{#if fields.length > 0}
		<div class="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
			{#each fields as field}
				<div class="min-w-0">
					<dt class="text-xs font-medium uppercase tracking-wider text-text-secondary">{field.label}</dt>
					<dd class="mt-0.5 truncate text-sm text-text-primary">{field.value}</dd>
				</div>
			{/each}
		</div>
	{/if}
</div>
