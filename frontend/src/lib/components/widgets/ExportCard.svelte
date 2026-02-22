<!--
  ExportCard.svelte - Download card for export results.

  Renders a card with title, format badge, row count, file size,
  download button, and status indicator for exports.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Download, Check, X, Loader2, FileDown } from 'lucide-svelte';

	interface ExportCardProps {
		export_id: string;
		title: string;
		format: 'csv' | 'json' | 'pdf';
		status: 'pending' | 'generating' | 'completed' | 'failed';
		row_count?: number;
		file_size?: number;
		error?: string;
	}

	let { export_id, title, format, status, row_count, file_size, error }: ExportCardProps =
		$props();

	// -----------------------------------------------------------------------
	// Format badge colours (using CSS variable-based colors)
	// -----------------------------------------------------------------------

	const formatBadge: Record<string, string> = {
		csv: 'bg-success/15 text-success border border-success/20',
		json: 'bg-accent/15 text-accent border border-accent/20',
		pdf: 'bg-danger/15 text-danger border border-danger/20'
	};

	let badgeClass = $derived(formatBadge[format] ?? formatBadge.csv);

	// -----------------------------------------------------------------------
	// File size formatter
	// -----------------------------------------------------------------------

	function formatBytes(bytes?: number): string {
		if (bytes == null || bytes === 0) return '--';
		const units = ['B', 'KB', 'MB', 'GB'];
		let i = 0;
		let size = bytes;
		while (size >= 1024 && i < units.length - 1) {
			size /= 1024;
			i++;
		}
		return `${i === 0 ? size : size.toFixed(1)} ${units[i]}`;
	}

	// -----------------------------------------------------------------------
	// Row count formatter
	// -----------------------------------------------------------------------

	function formatRowCount(count?: number): string {
		if (count == null) return '--';
		return count.toLocaleString();
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
	<!-- Header row: icon + title + format badge -->
	<div class="flex items-start justify-between gap-3">
		<div class="flex items-center gap-2.5 min-w-0">
			<span class="shrink-0 text-text-secondary">
				<FileDown size={18} />
			</span>
			<h3 class="truncate text-sm font-semibold text-text-primary">{title}</h3>
		</div>
		<span class="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase {badgeClass}">
			{format}
		</span>
	</div>

	<!-- Metadata: row count + file size -->
	<div class="mt-3 flex items-center gap-4 text-xs text-text-secondary">
		<span>Rows: {formatRowCount(row_count)}</span>
		<span>Size: {formatBytes(file_size)}</span>
	</div>

	<!-- Status + action row -->
	<div class="mt-4 flex items-center justify-between">
		<!-- Status indicator -->
		{#if status === 'generating' || status === 'pending'}
			<span class="inline-flex items-center gap-1.5 text-xs text-text-secondary">
				<Loader2 size={14} class="animate-spin" />
				{status === 'pending' ? 'Pending' : 'Generating'}...
			</span>
		{:else if status === 'completed'}
			<span class="inline-flex items-center gap-1.5 text-xs text-success">
				<Check size={14} />
				Completed
			</span>
		{:else if status === 'failed'}
			<span class="inline-flex items-center gap-1.5 text-xs text-danger">
				<X size={14} />
				Failed{#if error}: {error}{/if}
			</span>
		{/if}

		<!-- Download button -->
		{#if status === 'completed'}
			<a
				href="/api/exports/{export_id}/download"
				class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-all hover:bg-accent-hover"
			>
				<Download size={14} />
				Download
			</a>
		{:else}
			<button
				type="button"
				disabled
				class="inline-flex items-center gap-1.5 rounded-lg bg-accent/50 px-3 py-1.5 text-xs font-medium text-white/60 cursor-not-allowed"
			>
				<Download size={14} />
				Download
			</button>
		{/if}
	</div>
</div>
