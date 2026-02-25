<!--
  ModelStatus.svelte - Compact LLM model and connection indicator.

  Displays the active model name with a colored status dot. Clicking
  opens a small popover with provider details, latency, and fallback info.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Cpu, Zap, WifiOff, ChevronDown } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import { onMount } from 'svelte';

	interface LLMStatus {
		provider_name: string | null;
		provider_type: string | null;
		model: string | null;
		status: string;
		latency_ms: number | null;
		fallback_models: string[];
	}

	let status = $state<LLMStatus | null>(null);
	let popoverOpen = $state(false);
	let loading = $state(true);

	function formatModel(model: string | null): string {
		if (!model) return 'No model';
		// Strip common prefixes for display
		return model
			.replace(/^claude-/, '')
			.replace(/^gpt-/, 'GPT-')
			.replace(/-\d{8}$/, '');
	}

	const statusColors: Record<string, string> = {
		connected: 'bg-emerald-500',
		degraded: 'bg-yellow-500',
		disconnected: 'bg-red-500',
		unknown: 'bg-gray-400'
	};

	const statusLabels: Record<string, string> = {
		connected: 'Connected',
		degraded: 'Degraded',
		disconnected: 'Disconnected',
		unknown: 'Unknown'
	};

	async function fetchStatus() {
		try {
			status = await apiJson<LLMStatus>('/llm/status');
		} catch {
			status = { provider_name: null, provider_type: null, model: null, status: 'disconnected', latency_ms: null, fallback_models: [] };
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchStatus();
		// Refresh every 60 seconds
		const interval = setInterval(fetchStatus, 60_000);
		return () => clearInterval(interval);
	});

	function togglePopover() {
		popoverOpen = !popoverOpen;
	}

	function handleWindowClick(event: MouseEvent) {
		const target = event.target as HTMLElement;
		if (!target.closest('[data-model-status]')) {
			popoverOpen = false;
		}
	}
</script>

<svelte:window onclick={handleWindowClick} />

<div class="relative" data-model-status>
	<button
		type="button"
		onclick={togglePopover}
		class="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		title={status ? `${status.model} — ${statusLabels[status.status] ?? 'Unknown'}` : 'Loading...'}
	>
		{#if loading}
			<div class="h-2 w-2 animate-pulse rounded-full bg-gray-400"></div>
			<span class="hidden sm:inline">Loading...</span>
		{:else if status}
			<div class="relative flex h-2 w-2">
				<div class="h-2 w-2 rounded-full {statusColors[status.status] ?? statusColors.unknown}"></div>
				{#if status.status === 'connected'}
					<div class="absolute inset-0 animate-ping rounded-full {statusColors.connected} opacity-40"></div>
				{/if}
			</div>
			<span class="hidden sm:inline">{formatModel(status.model)}</span>
			<ChevronDown size={10} class="hidden opacity-50 sm:inline" />
		{/if}
	</button>

	{#if popoverOpen && status}
		<div
			class="absolute right-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-surface-elevated/95 p-3 shadow-xl backdrop-blur-xl"
		>
			<div class="flex flex-col gap-2.5">
				<!-- Model -->
				<div class="flex items-center gap-2">
					<Cpu size={14} class="shrink-0 text-text-secondary" />
					<div class="flex-1">
						<p class="text-xs font-medium text-text-primary">
							{status.model ?? 'No model configured'}
						</p>
						{#if status.provider_name}
							<p class="text-[10px] text-text-secondary">
								{status.provider_name} ({status.provider_type})
							</p>
						{/if}
					</div>
					<div
						class="rounded-full px-1.5 py-0.5 text-[10px] font-medium
							{status.status === 'connected'
							? 'bg-emerald-500/10 text-emerald-600'
							: status.status === 'degraded'
								? 'bg-yellow-500/10 text-yellow-600'
								: 'bg-red-500/10 text-red-600'}"
					>
						{statusLabels[status.status] ?? 'Unknown'}
					</div>
				</div>

				<!-- Latency -->
				{#if status.latency_ms !== null}
					<div class="flex items-center gap-2 text-[10px] text-text-secondary">
						<Zap size={10} />
						<span>Latency: {Math.round(status.latency_ms)}ms</span>
					</div>
				{/if}

				<!-- Fallback -->
				{#if status.fallback_models.length > 0}
					<div class="border-t border-border pt-2">
						<p class="mb-1 text-[10px] font-medium text-text-secondary">Fallback Models</p>
						<div class="flex flex-wrap gap-1">
							{#each status.fallback_models as fb}
								<span
									class="rounded bg-surface-secondary px-1.5 py-0.5 font-mono text-[10px] text-text-secondary"
								>
									{fb}
								</span>
							{/each}
						</div>
					</div>
				{/if}

				<!-- No provider -->
				{#if !status.provider_name}
					<div class="flex items-center gap-1.5 text-[10px] text-text-secondary">
						<WifiOff size={10} />
						<span>No LLM provider configured</span>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
