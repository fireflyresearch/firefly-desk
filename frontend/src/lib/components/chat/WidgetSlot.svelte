<!--
  WidgetSlot.svelte - Dispatches rendering to the correct widget component
  based on the directive type.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import type { WidgetDirective } from '$lib/stores/chat.js';
	import { getWidget } from '$lib/widgets/registry.js';

	interface WidgetSlotProps {
		directive: WidgetDirective;
	}

	let { directive }: WidgetSlotProps = $props();

	let Widget = $derived(getWidget(directive.type));
</script>

{#if Widget}
	<div
		class={directive.display === 'inline' ? 'inline-block align-middle' : 'my-2 w-full'}
		data-widget-id={directive.widget_id}
	>
		<Widget {...directive.props} />
	</div>
{:else}
	<div
		class="my-2 rounded-lg border border-border bg-surface-secondary px-4 py-2 text-xs text-text-secondary"
		data-widget-id={directive.widget_id}
	>
		Unknown widget type: {directive.type}
	</div>
{/if}
