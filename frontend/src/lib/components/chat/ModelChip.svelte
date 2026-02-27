<!--
  ModelChip.svelte - Inline model name/status indicator for the input bar.

  A subtle text chip showing the active model name with status dot.
  Lighter weight than ModelStatus, designed for inline use within InputBar.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { apiJson } from '$lib/services/api.js';
	import { onMount } from 'svelte';

	interface LLMStatus {
		model: string | null;
		status: string;
	}

	let status = $state<LLMStatus | null>(null);

	function formatModel(model: string | null): string {
		if (!model) return 'No model';
		return model
			.replace(/^claude-/, 'Claude ')
			.replace(/^gpt-/, 'GPT-')
			.replace(/-\d{8}$/, '')
			.replace(/-/g, ' ')
			.replace(/\b\w/g, (c) => c.toUpperCase());
	}

	const dotColor: Record<string, string> = {
		connected: 'bg-emerald-500',
		degraded: 'bg-yellow-500',
		disconnected: 'bg-red-500',
		unknown: 'bg-gray-400'
	};

	onMount(() => {
		apiJson<LLMStatus>('/llm/status')
			.then((s) => { status = s; })
			.catch(() => {
				status = { model: null, status: 'unknown' };
			});
	});
</script>

{#if status}
	<div class="flex items-center gap-1.5 px-1">
		<div class="h-1.5 w-1.5 rounded-full {dotColor[status.status] ?? dotColor.unknown}"></div>
		<span class="text-[11px] text-text-secondary/60">
			{formatModel(status.model)}
		</span>
	</div>
{/if}
