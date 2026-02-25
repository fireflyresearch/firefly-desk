<!--
  SSOUnifiedManager.svelte - Unified SSO management with tabs.

  Combines SSO Providers and Attribute Mappings into a single page
  with a tab bar for navigation between the two views.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Shield, ArrowLeftRight } from 'lucide-svelte';
	import SSOManager from './SSOManager.svelte';
	import SSOAttributeMapper from './SSOAttributeMapper.svelte';

	let activeTab = $state<'providers' | 'mappings'>('providers');
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div>
		<h1 class="text-lg font-semibold text-text-primary">Single Sign-On</h1>
		<p class="text-sm text-text-secondary">
			Manage OIDC providers and attribute mappings for SSO authentication
		</p>
	</div>

	<!-- Tab bar -->
	<div class="flex gap-1 border-b border-border">
		<button
			type="button"
			onclick={() => (activeTab = 'providers')}
			class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'providers'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			<Shield size={14} />
			Providers
		</button>
		<button
			type="button"
			onclick={() => (activeTab = 'mappings')}
			class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'mappings'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			<ArrowLeftRight size={14} />
			Attribute Mappings
		</button>
	</div>

	<!-- Tab content -->
	<div class="flex-1 overflow-y-auto">
		{#if activeTab === 'providers'}
			<SSOManager embedded={true} />
		{:else}
			<SSOAttributeMapper embedded={true} />
		{/if}
	</div>
</div>
