<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import AppShell from '$lib/components/layout/AppShell.svelte';
	import PanelContainer from '$lib/components/panels/PanelContainer.svelte';
	import { panelVisible } from '$lib/stores/panel.js';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<AppShell panelVisible={$panelVisible}>
	{#snippet panel()}
		<PanelContainer />
	{/snippet}
	{@render children()}
</AppShell>
