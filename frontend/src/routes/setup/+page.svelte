<!--
  Setup Wizard page -- guides first-run configuration.
  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import SetupWizard from '$lib/components/setup/SetupWizard.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Setup - Firefly Desk</title>
</svelte:head>

<SetupWizard status={data.status} />
