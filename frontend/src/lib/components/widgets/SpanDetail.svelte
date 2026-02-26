<!--
  SpanDetail.svelte - Single span/trace detail view.

  Renders a comprehensive view of a single span including key-value
  attributes, timeline events, and span links.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface SpanEvent {
		name: string;
		timestamp: string | number;
		attributes?: Record<string, unknown>;
	}

	interface SpanLink {
		traceId: string;
		spanId: string;
		attributes?: Record<string, unknown>;
	}

	interface SpanData {
		traceId: string;
		spanId: string;
		operationName: string;
		serviceName: string;
		startTime: string | number;
		endTime: string | number;
		status: string;
		attributes?: Record<string, unknown>;
		events?: SpanEvent[];
		links?: SpanLink[];
	}

	interface SpanDetailProps {
		span: SpanData;
	}

	let { span }: SpanDetailProps = $props();

	// -----------------------------------------------------------------
	// Computed values
	// -----------------------------------------------------------------

	let duration = $derived.by(() => {
		const start = new Date(span.startTime).getTime();
		const end = new Date(span.endTime).getTime();
		if (isNaN(start) || isNaN(end)) return null;
		return end - start;
	});

	let statusClass = $derived.by(() => {
		const s = span.status.toLowerCase();
		if (s === 'ok' || s === 'success') return { text: 'text-success', bg: 'bg-success/10 text-success' };
		if (s === 'error') return { text: 'text-danger', bg: 'bg-danger/10 text-danger' };
		return { text: 'text-accent', bg: 'bg-accent/10 text-accent' };
	});

	let attributeEntries = $derived(
		span.attributes ? Object.entries(span.attributes) : []
	);

	// -----------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------

	function formatDuration(ms: number): string {
		if (ms < 1) return `${(ms * 1000).toFixed(0)}\u00B5s`;
		if (ms < 1000) return `${ms.toFixed(1)}ms`;
		return `${(ms / 1000).toFixed(2)}s`;
	}

	function formatTimestamp(ts: string | number): string {
		const d = new Date(ts);
		if (isNaN(d.getTime())) return String(ts);
		return d.toLocaleString();
	}

	function formatValue(value: unknown): string {
		if (value === null || value === undefined) return '';
		if (typeof value === 'object') return JSON.stringify(value);
		return String(value);
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	<!-- Header -->
	<div class="border-b border-border px-4 py-3">
		<div class="flex items-center justify-between gap-3">
			<h3 class="text-sm font-semibold text-text-primary">{span.operationName}</h3>
			<span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase {statusClass.bg}">
				{span.status}
			</span>
		</div>
		<p class="mt-0.5 text-xs text-text-secondary">{span.serviceName}</p>
	</div>

	<!-- Overview fields -->
	<div class="border-b border-border">
		<dl class="divide-y divide-border">
			<div class="flex items-baseline justify-between gap-4 px-4 py-2.5">
				<dt class="shrink-0 text-[10px] font-medium uppercase tracking-wider text-text-secondary">Trace ID</dt>
				<dd class="truncate text-right text-xs font-mono text-text-primary">{span.traceId}</dd>
			</div>
			<div class="flex items-baseline justify-between gap-4 px-4 py-2.5">
				<dt class="shrink-0 text-[10px] font-medium uppercase tracking-wider text-text-secondary">Span ID</dt>
				<dd class="truncate text-right text-xs font-mono text-text-primary">{span.spanId}</dd>
			</div>
			<div class="flex items-baseline justify-between gap-4 px-4 py-2.5">
				<dt class="shrink-0 text-[10px] font-medium uppercase tracking-wider text-text-secondary">Start Time</dt>
				<dd class="text-right text-xs text-text-primary">{formatTimestamp(span.startTime)}</dd>
			</div>
			<div class="flex items-baseline justify-between gap-4 px-4 py-2.5">
				<dt class="shrink-0 text-[10px] font-medium uppercase tracking-wider text-text-secondary">End Time</dt>
				<dd class="text-right text-xs text-text-primary">{formatTimestamp(span.endTime)}</dd>
			</div>
			{#if duration !== null}
				<div class="flex items-baseline justify-between gap-4 px-4 py-2.5">
					<dt class="shrink-0 text-[10px] font-medium uppercase tracking-wider text-text-secondary">Duration</dt>
					<dd class="text-right text-xs font-semibold {statusClass.text} tabular-nums">{formatDuration(duration)}</dd>
				</div>
			{/if}
			<div class="flex items-baseline justify-between gap-4 px-4 py-2.5">
				<dt class="shrink-0 text-[10px] font-medium uppercase tracking-wider text-text-secondary">Status</dt>
				<dd class="text-right">
					<span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase {statusClass.bg}">
						{span.status}
					</span>
				</dd>
			</div>
		</dl>
	</div>

	<!-- Attributes -->
	{#if attributeEntries.length > 0}
		<div class="border-b border-border">
			<div class="px-4 py-2.5 border-b border-border/50">
				<h4 class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">Attributes</h4>
			</div>
			<dl class="divide-y divide-border/50">
				{#each attributeEntries as [key, value]}
					<div class="flex items-baseline justify-between gap-4 px-4 py-2">
						<dt class="shrink-0 text-[10px] font-medium text-text-secondary">{key}</dt>
						<dd class="truncate text-right text-[10px] font-mono text-text-primary">{formatValue(value)}</dd>
					</div>
				{/each}
			</dl>
		</div>
	{/if}

	<!-- Events -->
	{#if span.events && span.events.length > 0}
		<div class="border-b border-border">
			<div class="px-4 py-2.5 border-b border-border/50">
				<h4 class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">Events</h4>
			</div>
			<div class="divide-y divide-border/50">
				{#each span.events as event}
					<div class="px-4 py-2">
						<div class="flex items-center justify-between gap-3">
							<span class="text-xs font-medium text-text-primary">{event.name}</span>
							<time class="text-[10px] font-mono tabular-nums text-text-secondary">{formatTimestamp(event.timestamp)}</time>
						</div>
						{#if event.attributes && Object.keys(event.attributes).length > 0}
							<div class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 pl-2">
								{#each Object.entries(event.attributes) as [key, value]}
									<span class="text-[10px] text-text-secondary">{key}</span>
									<span class="text-[10px] font-mono text-text-primary truncate">{formatValue(value)}</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Links -->
	{#if span.links && span.links.length > 0}
		<div>
			<div class="px-4 py-2.5 border-b border-border/50">
				<h4 class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">Linked Spans</h4>
			</div>
			<div class="divide-y divide-border/50">
				{#each span.links as link}
					<div class="px-4 py-2">
						<div class="flex items-baseline gap-3">
							<span class="text-[10px] font-medium text-text-secondary">Trace</span>
							<span class="text-[10px] font-mono text-text-primary truncate">{link.traceId}</span>
						</div>
						<div class="flex items-baseline gap-3 mt-0.5">
							<span class="text-[10px] font-medium text-text-secondary">Span</span>
							<span class="text-[10px] font-mono text-text-primary truncate">{link.spanId}</span>
						</div>
						{#if link.attributes && Object.keys(link.attributes).length > 0}
							<div class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 pl-2">
								{#each Object.entries(link.attributes) as [key, value]}
									<span class="text-[10px] text-text-secondary">{key}</span>
									<span class="text-[10px] font-mono text-text-primary truncate">{formatValue(value)}</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
