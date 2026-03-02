<!--
  Admin - System Catalog page with tabs.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Server, Radar, Tags, Upload } from 'lucide-svelte';
	import CatalogManager from '$lib/components/admin/CatalogManager.svelte';

	type Tab = 'systems' | 'discovery' | 'tags' | 'import';
	let activeTab = $state<Tab>('systems');

	const tabs: Array<{ key: Tab; label: string; icon: typeof Server; description: string }> = [
		{ key: 'systems', label: 'Systems', icon: Server, description: 'Manage external systems and endpoints' },
		{ key: 'discovery', label: 'Discovery', icon: Radar, description: 'AI-powered system detection' },
		{ key: 'tags', label: 'Tags', icon: Tags, description: 'Manage system tags' },
		{ key: 'import', label: 'Import', icon: Upload, description: 'Import systems from curl or OpenAPI' },
	];
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 border-b border-border/30 bg-surface-secondary/30 px-6 pt-5 pb-0">
		<h1 class="mb-1 text-lg font-semibold text-text-primary">System Catalog</h1>
		<p class="mb-4 text-sm text-text-secondary">Manage external systems, discovery, tags, and imports.</p>

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
		<CatalogManager activeView={activeTab} />
	</div>
</div>
