<!--
  App group layout -- wraps all authenticated routes in the AppShell.

  On mount, checks whether initial setup has been completed. If not,
  redirects to the /setup wizard before rendering any app content.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import AppShell from '$lib/components/layout/AppShell.svelte';
	import PanelContainer from '$lib/components/panels/PanelContainer.svelte';
	import { panelVisible } from '$lib/stores/panel.js';
	import { initCurrentUser } from '$lib/stores/user.js';
	import { onMount } from 'svelte';

	let { children } = $props();
	let setupChecked = $state(false);

	$effect(() => {
		initCurrentUser();
	});

	onMount(async () => {
		try {
			const res = await fetch('/api/setup/status');
			if (res.ok) {
				const status = await res.json();
				if (!status.setup_completed) {
					window.location.href = '/setup';
					return;
				}
			}
		} catch {
			// If check fails, proceed normally
		}
		setupChecked = true;
	});
</script>

{#if setupChecked}
	<AppShell panelVisible={$panelVisible}>
		{#snippet panel()}
			<PanelContainer />
		{/snippet}
		{@render children()}
	</AppShell>
{/if}
