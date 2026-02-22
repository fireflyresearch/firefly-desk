<!--
  Root layout -- CSS imports and favicon only.
  The AppShell is applied by the (app) group layout, so that
  auth and setup pages render standalone.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { initTheme, resolvedTheme } from '$lib/stores/theme';

	let { children } = $props();

	onMount(() => {
		initTheme();
	});

	$effect(() => {
		document.documentElement.dataset.theme = $resolvedTheme;
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
