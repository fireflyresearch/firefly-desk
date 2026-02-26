<!--
  LogViewer.svelte - Structured log display with level-based filtering.

  Renders a scrollable log list with level-based coloring, expandable
  attribute rows, and filter buttons for each log level.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ChevronRight } from 'lucide-svelte';

	interface LogEntry {
		timestamp: string;
		level: string;
		message: string;
		service?: string;
		traceId?: string;
		attributes?: Record<string, unknown>;
	}

	interface LogViewerProps {
		logs: LogEntry[];
		title?: string;
	}

	let { logs, title }: LogViewerProps = $props();

	// -----------------------------------------------------------------
	// Level filter state
	// -----------------------------------------------------------------

	const ALL_LEVELS = ['ERROR', 'WARN', 'INFO', 'DEBUG'] as const;

	let enabledLevels = $state<Set<string>>(new Set(ALL_LEVELS));

	function toggleLevel(level: string) {
		const next = new Set(enabledLevels);
		if (next.has(level)) {
			next.delete(level);
		} else {
			next.add(level);
		}
		enabledLevels = next;
	}

	let filteredLogs = $derived(
		logs
			.map((log, originalIndex) => ({ log, originalIndex }))
			.filter(({ log }) => enabledLevels.has(normalizeLevel(log.level)))
	);

	// -----------------------------------------------------------------
	// Expanded rows for attributes
	// -----------------------------------------------------------------

	let expandedRows = $state<Set<string>>(new Set());

	function toggleRow(key: string) {
		const next = new Set(expandedRows);
		if (next.has(key)) {
			next.delete(key);
		} else {
			next.add(key);
		}
		expandedRows = next;
	}

	// -----------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------

	function normalizeLevel(level: string): string {
		const upper = level.toUpperCase();
		if (upper === 'WARNING') return 'WARN';
		if (ALL_LEVELS.includes(upper as (typeof ALL_LEVELS)[number])) return upper;
		return 'INFO';
	}

	function levelColor(level: string): string {
		const l = normalizeLevel(level);
		if (l === 'ERROR') return 'text-danger';
		if (l === 'WARN') return 'text-warning';
		if (l === 'INFO') return 'text-accent';
		return 'text-text-secondary';
	}

	function levelBgColor(level: string): string {
		const l = normalizeLevel(level);
		if (l === 'ERROR') return 'bg-danger/10 text-danger';
		if (l === 'WARN') return 'bg-warning/10 text-warning';
		if (l === 'INFO') return 'bg-accent/10 text-accent';
		return 'bg-text-secondary/10 text-text-secondary';
	}

	function filterBtnClass(level: string): string {
		const base = 'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase transition-opacity cursor-pointer';
		if (enabledLevels.has(level)) {
			return `${base} ${levelBgColor(level)}`;
		}
		return `${base} bg-surface-secondary/50 text-text-secondary opacity-40`;
	}

	function hasAttributes(log: LogEntry): boolean {
		return !!log.attributes && Object.keys(log.attributes).length > 0;
	}

	function formatValue(value: unknown): string {
		if (value === null || value === undefined) return '';
		if (typeof value === 'object') return JSON.stringify(value);
		return String(value);
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	<!-- Header -->
	<div class="border-b border-border px-4 py-3 flex items-center justify-between gap-3">
		{#if title}
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		{/if}
		<!-- Level filter buttons -->
		<div class="flex items-center gap-1.5">
			{#each ALL_LEVELS as level}
				<button
					type="button"
					class={filterBtnClass(level)}
					onclick={() => toggleLevel(level)}
				>
					{level}
				</button>
			{/each}
		</div>
	</div>

	<!-- Log entries -->
	<div class="max-h-[400px] overflow-y-auto divide-y divide-border">
		{#each filteredLogs as { log, originalIndex }}
			{@const rowKey = originalIndex.toString()}
			{@const hasAttrs = hasAttributes(log)}
			<div class="group">
				<!-- Main log row -->
				<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
				<div
					class="flex items-start gap-3 px-4 py-2 hover:bg-surface-secondary/30 transition-colors {hasAttrs ? 'cursor-pointer' : ''}"
					role={hasAttrs ? 'button' : undefined}
					tabindex={hasAttrs ? 0 : undefined}
					onclick={() => hasAttrs && toggleRow(rowKey)}
					onkeydown={(e) => hasAttrs && (e.key === 'Enter' || e.key === ' ') && toggleRow(rowKey)}
				>
					<!-- Expand chevron -->
					{#if hasAttrs}
						<span class="shrink-0 mt-0.5 text-text-secondary transition-transform {expandedRows.has(rowKey) ? 'rotate-90' : ''}">
							<ChevronRight size={12} />
						</span>
					{:else}
						<span class="shrink-0 w-3"></span>
					{/if}

					<!-- Timestamp -->
					<span class="shrink-0 text-[10px] font-mono tabular-nums text-text-secondary mt-0.5 w-[140px]">
						{log.timestamp}
					</span>

					<!-- Level badge -->
					<span class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase {levelBgColor(log.level)}">
						{normalizeLevel(log.level)}
					</span>

					<!-- Service -->
					{#if log.service}
						<span class="shrink-0 text-[10px] font-medium text-text-secondary truncate max-w-[100px]">
							{log.service}
						</span>
					{/if}

					<!-- Message -->
					<span class="flex-1 text-xs text-text-primary min-w-0 truncate {levelColor(log.level)}">
						{log.message}
					</span>
				</div>

				<!-- Expanded attributes -->
				{#if hasAttrs && expandedRows.has(rowKey)}
					<div class="bg-surface-secondary/20 px-4 py-2 pl-12 border-t border-border/50">
						{#if log.traceId}
							<div class="flex items-baseline gap-2 mb-1">
								<span class="text-[10px] font-medium uppercase tracking-wider text-text-secondary">Trace ID</span>
								<span class="text-[10px] font-mono text-text-primary">{log.traceId}</span>
							</div>
						{/if}
						<div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
							{#each Object.entries(log.attributes ?? {}) as [key, value]}
								<span class="text-[10px] font-medium text-text-secondary">{key}</span>
								<span class="text-[10px] font-mono text-text-primary truncate">{formatValue(value)}</span>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{:else}
			<div class="flex items-center justify-center py-8">
				<span class="text-xs text-text-secondary">No log entries to display</span>
			</div>
		{/each}
	</div>
</div>
