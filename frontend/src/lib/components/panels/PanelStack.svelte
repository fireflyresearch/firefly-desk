<!--
  PanelStack.svelte - Renders the top panel item from the panel stack
  and handles keyboard navigation (Esc to close, Backspace to go back).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { panelStack, popPanel, closePanel } from '$lib/stores/panel.js';
	import { getWidget } from '$lib/widgets/registry.js';
	import { get } from 'svelte/store';

	let stack: typeof import('$lib/stores/panel.js').PanelItem[] = $state([]);

	$effect(() => {
		const unsub = panelStack.subscribe((value) => {
			stack = value;
		});
		return unsub;
	});

	let current = $derived(stack.length > 0 ? stack[stack.length - 1] : null);
	let Widget = $derived(current ? getWidget(current.widgetType) : undefined);

	function handleKeydown(e: KeyboardEvent) {
		// Only handle keys when the panel has content
		if (stack.length === 0) return;

		// Ignore when user is typing in an input or textarea
		const tag = (e.target as HTMLElement)?.tagName;
		if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

		if (e.key === 'Escape') {
			e.preventDefault();
			closePanel();
		} else if (e.key === 'Backspace' && stack.length > 1) {
			e.preventDefault();
			popPanel();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="min-h-0 flex-1 overflow-y-auto p-4">
	{#if current && Widget}
		<div data-panel-id={current.id}>
			<Widget {...current.props} />
		</div>
	{:else if current}
		<div
			class="rounded-lg border border-border bg-surface-secondary px-4 py-2 text-xs text-text-secondary"
		>
			Unknown widget type: {current.widgetType}
		</div>
	{:else}
		<div class="flex h-full items-center justify-center text-sm text-text-secondary">
			No panel content
		</div>
	{/if}
</div>
