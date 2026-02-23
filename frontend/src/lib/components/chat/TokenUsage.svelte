<!--
  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->

<!--
  TokenUsage.svelte - Compact token usage display for assistant messages.

  Shows model name and total tokens in a subtle row that appears on hover.
  Expands on click to show full input/output token breakdown and estimated cost.
-->
<script lang="ts">
	import { Cpu } from 'lucide-svelte';
	import type { TokenUsage } from '$lib/stores/chat.js';

	interface TokenUsageProps {
		usage: TokenUsage;
	}

	let { usage }: TokenUsageProps = $props();
	let expanded = $state(false);

	function formatTokens(count: number): string {
		if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
		if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`;
		return count.toString();
	}

	function formatCost(usd: number): string {
		if (usd === 0) return '';
		if (usd < 0.01) return `$${usd.toFixed(4)}`;
		return `$${usd.toFixed(2)}`;
	}

	function formatModel(model: string): string {
		// Strip provider prefix (e.g. "openai:gpt-4o" -> "gpt-4o")
		const idx = model.indexOf(':');
		return idx >= 0 ? model.slice(idx + 1) : model;
	}

	let costDisplay = $derived(formatCost(usage.cost_usd));
</script>

<button
	type="button"
	class="mt-1 flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary"
	onclick={() => (expanded = !expanded)}
	title="Token usage"
>
	<Cpu size={12} class="shrink-0 opacity-60" />
	<span class="font-medium">{formatModel(usage.model)}</span>
	<span class="opacity-60">&middot;</span>
	<span>{formatTokens(usage.total_tokens)} tokens</span>
	{#if costDisplay}
		<span class="opacity-60">&middot;</span>
		<span>{costDisplay}</span>
	{/if}
</button>

{#if expanded}
	<div
		class="ml-1 mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-secondary"
	>
		<span>
			<span class="font-medium text-text-primary">Input:</span>
			{formatTokens(usage.input_tokens)}
		</span>
		<span>
			<span class="font-medium text-text-primary">Output:</span>
			{formatTokens(usage.output_tokens)}
		</span>
		<span>
			<span class="font-medium text-text-primary">Total:</span>
			{formatTokens(usage.total_tokens)}
		</span>
		{#if costDisplay}
			<span>
				<span class="font-medium text-text-primary">Cost:</span>
				{costDisplay}
			</span>
		{/if}
	</div>
{/if}
