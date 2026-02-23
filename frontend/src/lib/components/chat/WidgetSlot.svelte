<!--
  WidgetSlot.svelte - Dispatches rendering to the correct widget component
  based on the directive type. Wraps each widget in a fade-in animation
  and an error boundary that gracefully catches render failures.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { AlertTriangle } from 'lucide-svelte';
	import type { WidgetDirective } from '$lib/stores/chat.js';
	import { getWidget } from '$lib/widgets/registry.js';

	interface WidgetSlotProps {
		directive: WidgetDirective;
	}

	let { directive }: WidgetSlotProps = $props();

	let Widget = $derived(getWidget(directive.type));

	let renderError = $state<Error | null>(null);

	function handleError(error: unknown) {
		renderError = error instanceof Error ? error : new Error(String(error));
	}

	function handleRetry() {
		renderError = null;
	}
</script>

{#if Widget}
	<div
		class="widget-appear {directive.display === 'inline'
			? 'inline-block align-middle'
			: 'my-2 w-full'}"
		data-widget-id={directive.widget_id}
	>
		{#if renderError}
			<!-- Error fallback -->
			<div class="rounded-xl border border-danger/20 bg-danger/5 p-4">
				<div class="flex items-start gap-2.5">
					<span class="mt-0.5 shrink-0 text-danger">
						<AlertTriangle size={16} />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-sm font-semibold text-text-primary">
							Widget render error
						</p>
						<p class="mt-1 text-xs text-text-secondary">
							The <code class="rounded bg-surface-hover px-1 py-0.5 font-mono text-xs">{directive.type}</code> widget failed to render.
						</p>
						{#if renderError.message}
							<p class="mt-1 text-xs text-text-secondary/70 font-mono truncate">
								{renderError.message}
							</p>
						{/if}
						<button
							type="button"
							class="mt-2 rounded-lg border border-border bg-surface-secondary px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
							onclick={handleRetry}
						>
							Retry
						</button>
					</div>
				</div>
			</div>
		{:else}
			<svelte:boundary onerror={handleError}>
				<Widget {...directive.props} />
				{#snippet failed(error)}
					<!-- Svelte boundary caught a rendering error -->
					<div class="rounded-xl border border-danger/20 bg-danger/5 p-4">
						<div class="flex items-start gap-2.5">
							<span class="mt-0.5 shrink-0 text-danger">
								<AlertTriangle size={16} />
							</span>
							<div class="min-w-0">
								<p class="text-sm font-semibold text-text-primary">
									Widget render error
								</p>
								<p class="mt-1 text-xs text-text-secondary">
									Failed to render <code class="rounded bg-surface-hover px-1 py-0.5 font-mono text-xs">{directive.type}</code>
								</p>
							</div>
						</div>
					</div>
				{/snippet}
			</svelte:boundary>
		{/if}
	</div>
{:else}
	<div
		class="widget-appear my-2 rounded-xl border border-border bg-surface-secondary px-4 py-2 text-xs text-text-secondary"
		data-widget-id={directive.widget_id}
	>
		Unknown widget type: <code class="rounded bg-surface-hover px-1 py-0.5 font-mono">{directive.type}</code>
	</div>
{/if}

<style>
	@keyframes widget-fade-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.widget-appear {
		animation: widget-fade-in 0.3s ease-out both;
	}
</style>
