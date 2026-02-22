<!--
  App group layout -- wraps all authenticated routes in the AppShell.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import AppShell from '$lib/components/layout/AppShell.svelte';
	import PanelContainer from '$lib/components/panels/PanelContainer.svelte';
	import { panelVisible } from '$lib/stores/panel.js';
	import { initCurrentUser } from '$lib/stores/user.js';

	let { children } = $props();

	$effect(() => {
		initCurrentUser();
	});
</script>

<AppShell panelVisible={$panelVisible}>
	{#snippet panel()}
		<PanelContainer />
	{/snippet}
	{@render children()}
</AppShell>
