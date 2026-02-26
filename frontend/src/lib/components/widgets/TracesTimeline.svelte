<!--
  TracesTimeline.svelte - Display distributed traces as a waterfall/timeline.

  Renders horizontal bar chart with nested spans, duration labels, and
  status-based coloring. Supports hierarchical span trees via children.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface TraceSpan {
		traceId: string;
		spanId: string;
		operationName: string;
		serviceName: string;
		duration: number;
		startTime: number;
		status: string;
		children?: TraceSpan[];
	}

	interface TracesTimelineProps {
		traces: TraceSpan[];
		title?: string;
	}

	let { traces, title }: TracesTimelineProps = $props();

	// -----------------------------------------------------------------
	// Flatten the span tree into a display list with depth information
	// -----------------------------------------------------------------

	interface FlatSpan extends TraceSpan {
		depth: number;
	}

	function flattenSpans(spans: TraceSpan[], depth: number = 0): FlatSpan[] {
		const result: FlatSpan[] = [];
		for (const span of spans) {
			result.push({ ...span, depth });
			if (span.children && span.children.length > 0) {
				result.push(...flattenSpans(span.children, depth + 1));
			}
		}
		return result;
	}

	let flatSpans = $derived(flattenSpans(traces));

	// -----------------------------------------------------------------
	// Compute the global time range for scaling bars
	// -----------------------------------------------------------------

	let timeRange = $derived.by(() => {
		if (flatSpans.length === 0) return { min: 0, max: 1 };
		let min = Infinity;
		let max = -Infinity;
		for (const span of flatSpans) {
			if (span.startTime < min) min = span.startTime;
			const end = span.startTime + span.duration;
			if (end > max) max = end;
		}
		// Avoid division by zero
		if (max === min) max = min + 1;
		return { min, max };
	});

	// -----------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------

	function barLeft(span: FlatSpan): number {
		return ((span.startTime - timeRange.min) / (timeRange.max - timeRange.min)) * 100;
	}

	function barWidth(span: FlatSpan): number {
		return Math.max((span.duration / (timeRange.max - timeRange.min)) * 100, 0.5);
	}

	function statusColor(status: string): string {
		const s = status.toLowerCase();
		if (s === 'ok' || s === 'success') return 'bg-success';
		if (s === 'error') return 'bg-danger';
		return 'bg-accent';
	}

	function statusTextColor(status: string): string {
		const s = status.toLowerCase();
		if (s === 'ok' || s === 'success') return 'text-success';
		if (s === 'error') return 'text-danger';
		return 'text-accent';
	}

	function formatDuration(ms: number): string {
		if (ms < 1) return `${(ms * 1000).toFixed(0)}\u00B5s`;
		if (ms < 1000) return `${ms.toFixed(1)}ms`;
		return `${(ms / 1000).toFixed(2)}s`;
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="divide-y divide-border">
		{#each flatSpans as span}
			<div class="flex items-center gap-3 px-4 py-2 hover:bg-surface-secondary/30 transition-colors">
				<!-- Label column -->
				<div
					class="shrink-0 w-[200px] min-w-0"
					style:padding-left="{span.depth * 16}px"
				>
					<p class="text-xs font-medium text-text-primary truncate">
						{span.operationName}
					</p>
					<p class="text-[10px] text-text-secondary truncate">
						{span.serviceName}
					</p>
				</div>

				<!-- Waterfall bar -->
				<div class="relative flex-1 h-6 min-w-0">
					<div class="absolute inset-0 rounded bg-surface-secondary/30"></div>
					<div
						class="absolute top-0.5 bottom-0.5 rounded {statusColor(span.status)}"
						style:left="{barLeft(span)}%"
						style:width="{barWidth(span)}%"
					></div>
				</div>

				<!-- Duration / Status -->
				<div class="shrink-0 w-[80px] text-right">
					<span class="text-xs font-mono tabular-nums {statusTextColor(span.status)}">
						{formatDuration(span.duration)}
					</span>
				</div>
			</div>
		{:else}
			<div class="flex items-center justify-center py-8">
				<span class="text-xs text-text-secondary">No traces to display</span>
			</div>
		{/each}
	</div>
</div>
