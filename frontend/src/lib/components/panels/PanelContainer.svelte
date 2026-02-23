<!--
  PanelContainer.svelte - Full-height wrapper for the right-side detail panel.

  Composes PanelHeader and PanelStack. Shows an empty state when the
  panel stack is empty.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import PanelHeader from './PanelHeader.svelte';
	import PanelStack from './PanelStack.svelte';
	import { panelStack, popPanel, closePanel, type PanelItem } from '$lib/stores/panel.js';

	let stack: PanelItem[] = $state([]);

	$effect(() => {
		const unsub = panelStack.subscribe((value) => {
			stack = value;
		});
		return unsub;
	});

	let current = $derived(stack.length > 0 ? stack[stack.length - 1] : null);
	let depth = $derived(stack.length);
</script>

<div class="flex h-full flex-col bg-surface">
	{#if current}
		<PanelHeader
			title={current.title}
			{depth}
			onBack={popPanel}
			onClose={closePanel}
		/>
		<PanelStack />
	{:else}
		<div class="flex h-full items-center justify-center text-sm text-text-secondary">
			No panel content
		</div>
	{/if}
</div>
