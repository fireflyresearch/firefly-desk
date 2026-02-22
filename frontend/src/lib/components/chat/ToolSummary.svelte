<!--
  ToolSummary.svelte - Collapsible summary of tool executions.

  Shows a compact "Used N tools in X.Xs" line that expands on click to
  reveal each tool's name, duration, and status.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ChevronRight, ChevronDown, Wrench, Check, X } from 'lucide-svelte';
	import type { ToolExecution } from '$lib/stores/tools.js';

	interface ToolSummaryProps {
		tools: ToolExecution[];
	}

	let { tools }: ToolSummaryProps = $props();

	let expanded = $state(false);

	let totalDuration = $derived(() => {
		const total = tools.reduce((sum, t) => sum + (t.duration ?? 0), 0);
		return total >= 1000 ? `${(total / 1000).toFixed(1)}s` : `${total}ms`;
	});

	let toolCount = $derived(tools.length);

	function formatDuration(ms?: number): string {
		if (ms === undefined) return '...';
		return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
	}

	function toggle() {
		expanded = !expanded;
	}
</script>

<div class="mt-2 rounded-lg border border-border bg-surface-secondary/50 p-3">
	<!-- Collapsed header -->
	<button
		type="button"
		class="flex w-full items-center gap-2 text-xs text-text-secondary hover:text-text-primary"
		onclick={toggle}
	>
		{#if expanded}
			<ChevronDown size={14} />
		{:else}
			<ChevronRight size={14} />
		{/if}
		<span>Used {toolCount} tool{toolCount !== 1 ? 's' : ''} in {totalDuration()}</span>
	</button>

	<!-- Expanded list -->
	{#if expanded}
		<div class="mt-2 flex flex-col gap-1.5">
			{#each tools as tool}
				<div class="flex items-center gap-2 text-xs">
					<Wrench size={12} class="shrink-0 text-text-secondary" />
					<span class="flex-1 text-text-primary">{tool.toolName}</span>
					<span class="rounded-full bg-surface-secondary px-2 text-text-secondary">
						{formatDuration(tool.duration)}
					</span>
					{#if tool.status === 'completed'}
						<Check size={12} class="text-success" />
					{:else if tool.status === 'error'}
						<X size={12} class="text-danger" />
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
