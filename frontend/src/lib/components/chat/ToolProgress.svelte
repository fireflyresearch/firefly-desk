<!--
  ToolProgress.svelte - Shows when a tool is being executed.

  Displays a horizontal bar with the tool name, an animated spinner, and
  optional status text.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2 } from 'lucide-svelte';

	interface ToolProgressProps {
		toolName: string;
		status?: string;
	}

	let { toolName, status }: ToolProgressProps = $props();
</script>

<div class="flex items-center gap-2 rounded-lg border border-border bg-surface-secondary px-3 py-2 mx-4 my-1">
	<span class="tool-spinner text-accent">
		<Loader2 size={16} />
	</span>
	<span class="text-xs font-medium text-text-primary">{toolName}</span>
	{#if status}
		<span class="text-xs text-text-secondary">{status}</span>
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
