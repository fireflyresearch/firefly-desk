<!--
  ProgressBar.svelte - Animated progress bar with variant support and indeterminate mode.

  Supports determinate (value/max) and indeterminate (value is null) modes.
  Variants control the fill color: default (accent), success, warning, danger.
  Includes a smooth CSS transition for fill changes and a shimmer animation
  for indeterminate state.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface ProgressBarProps {
		value?: number | null;
		max?: number;
		label?: string;
		variant?: 'default' | 'success' | 'warning' | 'danger';
	}

	let { value = null, max = 100, label, variant = 'default' }: ProgressBarProps = $props();

	let isIndeterminate = $derived(value == null);
	let clampedValue = $derived(Math.min(Math.max(value ?? 0, 0), max));
	let percentage = $derived(max > 0 ? Math.round((clampedValue / max) * 100) : 0);

	const fillColors: Record<NonNullable<ProgressBarProps['variant']>, string> = {
		default: 'bg-accent',
		success: 'bg-success',
		warning: 'bg-ember',
		danger: 'bg-danger'
	};

	const trackColors: Record<NonNullable<ProgressBarProps['variant']>, string> = {
		default: 'bg-accent/15',
		success: 'bg-success/15',
		warning: 'bg-ember/15',
		danger: 'bg-danger/15'
	};

	let fillColor = $derived(fillColors[variant ?? 'default']);
	let trackColor = $derived(trackColors[variant ?? 'default']);
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm">
	<!-- Label + percentage row -->
	<div class="flex items-center justify-between gap-2 mb-2">
		{#if label}
			<span class="text-sm font-semibold text-text-primary truncate">{label}</span>
		{:else}
			<span></span>
		{/if}
		{#if !isIndeterminate}
			<span class="shrink-0 text-xs font-medium text-text-secondary tabular-nums">
				{percentage}%
			</span>
		{/if}
	</div>

	<!-- Track -->
	<div
		class="relative h-2.5 w-full overflow-hidden rounded-full {trackColor}"
		role="progressbar"
		aria-valuenow={isIndeterminate ? undefined : clampedValue}
		aria-valuemin={0}
		aria-valuemax={max}
		aria-label={label ?? 'Progress'}
	>
		{#if isIndeterminate}
			<!-- Indeterminate shimmer -->
			<div class="progress-indeterminate absolute inset-0 rounded-full {fillColor}"></div>
		{:else}
			<!-- Determinate fill -->
			<div
				class="h-full rounded-full {fillColor} transition-all duration-500 ease-out"
				style="width: {percentage}%"
			></div>
		{/if}
	</div>
</div>

<style>
	@keyframes progress-shimmer {
		0% { transform: translateX(-100%); }
		100% { transform: translateX(250%); }
	}

	.progress-indeterminate {
		width: 40%;
		animation: progress-shimmer 1.5s ease-in-out infinite;
	}
</style>
