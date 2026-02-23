<!--
  MetricCard.svelte - Dashboard-style metric card grid.

  Renders a responsive grid of metric tiles, each showing a large value,
  a small label, an optional delta with trend arrow (green for up, red
  for down), and an optional icon. The grid adapts from 1 column on
  narrow containers to 2-4 columns on wider ones.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { TrendingUp, TrendingDown, Activity } from 'lucide-svelte';

	interface Metric {
		label: string;
		value: string;
		delta?: string;
		trend?: 'up' | 'down';
		icon?: string;
	}

	interface MetricCardProps {
		metrics: Metric[];
	}

	let { metrics }: MetricCardProps = $props();

	/** Determine grid columns class based on metric count. */
	let gridClass = $derived.by(() => {
		const count = metrics.length;
		if (count <= 1) return 'grid-cols-1';
		if (count === 2) return 'grid-cols-1 sm:grid-cols-2';
		if (count === 3) return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3';
		return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';
	});
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm">
	<div class="grid gap-4 {gridClass}">
		{#each metrics as metric}
			<div class="flex flex-col gap-1.5 rounded-lg border border-border/50 bg-surface p-4">
				<!-- Icon + Label row -->
				<div class="flex items-center gap-2">
					<span class="shrink-0 text-accent">
						<Activity size={14} />
					</span>
					<span class="truncate text-xs font-medium text-text-secondary">
						{metric.label}
					</span>
				</div>

				<!-- Value -->
				<p class="text-2xl font-bold text-text-primary tabular-nums tracking-tight">
					{metric.value}
				</p>

				<!-- Delta + Trend -->
				{#if metric.delta}
					<div
						class="flex items-center gap-1 text-xs font-medium {metric.trend === 'up'
							? 'text-success'
							: metric.trend === 'down'
								? 'text-danger'
								: 'text-text-secondary'}"
					>
						{#if metric.trend === 'up'}
							<TrendingUp size={12} />
						{:else if metric.trend === 'down'}
							<TrendingDown size={12} />
						{/if}
						<span>{metric.delta}</span>
					</div>
				{/if}
			</div>
		{/each}
	</div>
</div>
