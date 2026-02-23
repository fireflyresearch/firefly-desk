<!--
  ToolProgress.svelte - Shows when a tool is being executed.

  Displays a horizontal bar with the tool name, an animated spinner, elapsed
  timer, and optional status text. Expandable to show tool arguments and
  result preview.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { slide } from 'svelte/transition';
	import { Loader2, ChevronRight, ChevronDown } from 'lucide-svelte';

	interface ToolProgressProps {
		toolName: string;
		status?: string;
		args?: Record<string, unknown>;
		result?: Record<string, unknown>;
	}

	let { toolName, status, args, result }: ToolProgressProps = $props();

	let elapsed = $state(0);
	let expanded = $state(false);

	// Elapsed timer - updates every 100ms
	$effect(() => {
		const id = setInterval(() => {
			elapsed += 0.1;
		}, 100);
		return () => clearInterval(id);
	});

	let elapsedDisplay = $derived(elapsed < 10 ? elapsed.toFixed(1) : Math.round(elapsed).toString());

	let hasDetails = $derived(
		(args !== undefined && Object.keys(args).length > 0) || result !== undefined
	);

	function toggle() {
		if (hasDetails) {
			expanded = !expanded;
		}
	}

	function formatJson(obj: Record<string, unknown>): string {
		try {
			return JSON.stringify(obj, null, 2);
		} catch {
			return String(obj);
		}
	}

	function truncateResult(obj: Record<string, unknown>): string {
		const json = formatJson(obj);
		if (json.length > 500) {
			return json.slice(0, 500) + '\n...';
		}
		return json;
	}
</script>

<div class="mx-4 my-1">
	<!-- Header bar -->
	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-lg border border-border bg-surface-secondary px-3 py-2 transition-colors {hasDetails
			? 'cursor-pointer hover:bg-surface-secondary/80'
			: 'cursor-default'}"
		onclick={toggle}
	>
		{#if hasDetails}
			<span class="shrink-0 text-text-secondary">
				{#if expanded}
					<ChevronDown size={14} />
				{:else}
					<ChevronRight size={14} />
				{/if}
			</span>
		{/if}
		<span class="tool-spinner text-accent">
			<Loader2 size={16} />
		</span>
		<span class="text-xs font-medium text-text-primary">{toolName}</span>
		{#if status}
			<span class="text-xs text-text-secondary">{status}</span>
		{/if}
		<!-- Spacer -->
		<span class="flex-1"></span>
		<!-- Elapsed timer -->
		<span class="font-mono text-xs text-text-secondary tabular-nums">{elapsedDisplay}s</span>
	</button>

	<!-- Expandable detail -->
	{#if expanded && hasDetails}
		<div
			class="rounded-b-lg border border-t-0 border-border bg-surface-secondary/30 px-3 py-2"
			transition:slide={{ duration: 200 }}
		>
			{#if args && Object.keys(args).length > 0}
				<div class="mb-2">
					<span class="text-xs font-medium text-text-secondary">Arguments</span>
					<pre
						class="mt-1 max-h-40 overflow-auto rounded-md bg-surface-secondary p-2 text-xs text-text-primary">{formatJson(
							args
						)}</pre>
				</div>
			{/if}
			{#if result}
				<div>
					<span class="text-xs font-medium text-text-secondary">Result Preview</span>
					<pre
						class="mt-1 max-h-40 overflow-auto rounded-md bg-surface-secondary p-2 text-xs text-text-primary">{truncateResult(
							result
						)}</pre>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	.tool-spinner {
		display: inline-flex;
		animation: spin 1s linear infinite;
	}
</style>
