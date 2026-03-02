<!--
  Admin - LLM Configuration page with tabs.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Cpu, Route, Box } from 'lucide-svelte';
	import LLMProviderManager from '$lib/components/admin/LLMProviderManager.svelte';
	import ModelRoutingConfig from '$lib/components/admin/ModelRoutingConfig.svelte';

	type Tab = 'providers' | 'routing' | 'embedding';
	let activeTab = $state<Tab>('providers');

	const tabs: Array<{ key: Tab; label: string; icon: typeof Cpu; description: string }> = [
		{ key: 'providers', label: 'Providers', icon: Cpu, description: 'Manage LLM providers and API keys' },
		{ key: 'routing', label: 'Model Routing', icon: Route, description: 'Smart routing for cost optimization' },
		{ key: 'embedding', label: 'Embedding', icon: Box, description: 'Configure embedding models' },
	];
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 border-b border-border/30 bg-surface-secondary/30 px-6 pt-5 pb-0">
		<h1 class="mb-1 text-lg font-semibold text-text-primary">LLM Configuration</h1>
		<p class="mb-4 text-sm text-text-secondary">Manage language model providers, smart routing, and embeddings.</p>

		<!-- Tab bar -->
		<div class="flex gap-1">
			{#each tabs as tab}
				<button
					type="button"
					onclick={() => (activeTab = tab.key)}
					class="group relative flex items-center gap-2 rounded-t-lg px-4 py-2.5 text-sm font-medium transition-all
						{activeTab === tab.key
						? 'bg-surface text-text-primary shadow-[0_-1px_3px_rgba(0,0,0,0.04)]'
						: 'text-text-secondary hover:bg-surface-hover/40 hover:text-text-primary'}"
				>
					<tab.icon size={15} class={activeTab === tab.key ? 'text-accent' : 'text-text-secondary/50'} />
					{tab.label}
					{#if activeTab === tab.key}
						<div class="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-accent"></div>
					{/if}
				</button>
			{/each}
		</div>
	</div>

	<!-- Tab content -->
	<div class="min-h-0 flex-1 overflow-y-auto">
		{#if activeTab === 'providers'}
			<LLMProviderManager hideEmbedding={true} />
		{:else if activeTab === 'routing'}
			<ModelRoutingConfig />
		{:else if activeTab === 'embedding'}
			<LLMProviderManager embeddingOnly={true} />
		{/if}
	</div>
</div>
