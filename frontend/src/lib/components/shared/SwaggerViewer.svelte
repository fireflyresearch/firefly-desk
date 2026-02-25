<!--
  SwaggerViewer.svelte - Renders an OpenAPI spec using Swagger UI.

  Dynamically imports swagger-ui-bundle to avoid SSR issues and renders
  a read-only API documentation view. Falls back to formatted JSON when
  Swagger UI fails to load.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		spec: string;
	}

	let { spec }: Props = $props();

	let containerEl: HTMLDivElement | undefined = $state();
	let error = $state('');
	let loading = $state(true);
	let fallbackContent: string | null = $state(null);

	onMount(async () => {
		if (!containerEl) return;

		let specObj: object | undefined;

		try {
			// Parse spec (could be JSON or YAML-ish)
			try {
				specObj = JSON.parse(spec);
			} catch {
				// If not valid JSON, show raw content as fallback
				error = 'Could not parse OpenAPI spec as JSON. Raw content shown below.';
				fallbackContent = spec;
				loading = false;
				return;
			}

			// Dynamically import swagger-ui to avoid SSR issues
			// @ts-ignore -- swagger-ui-dist has no type declarations
			const SwaggerUIBundle = (await import('swagger-ui-dist/swagger-ui-bundle.js')).default;

			// Import CSS
			await import('swagger-ui-dist/swagger-ui.css');

			SwaggerUIBundle({
				spec: specObj,
				domNode: containerEl,
				presets: [SwaggerUIBundle.presets.apis],
				layout: 'BaseLayout',
				supportedSubmitMethods: [], // Read-only: no "Try it out"
				defaultModelsExpandDepth: 1,
				docExpansion: 'list'
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load Swagger UI';
			// Show parsed JSON as fallback when Swagger UI itself fails to load
			if (specObj) {
				fallbackContent = JSON.stringify(specObj, null, 2);
			}
		} finally {
			loading = false;
		}
	});
</script>

<div class="swagger-viewer">
	{#if loading}
		<div class="flex items-center justify-center py-8">
			<div
				class="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent"
			></div>
			<span class="ml-2 text-sm text-text-secondary">Loading API documentation...</span>
		</div>
	{/if}

	{#if error}
		<div class="mb-3 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-warning">
			{error}
		</div>
	{/if}

	{#if fallbackContent}
		<pre class="max-h-[60vh] overflow-auto rounded-lg border border-border bg-surface-secondary p-4 text-xs leading-relaxed text-text-primary">{fallbackContent}</pre>
	{/if}

	<div bind:this={containerEl} class="swagger-ui-container"></div>
</div>

<style>
	.swagger-viewer :global(.swagger-ui) {
		font-family: inherit;
	}
	.swagger-viewer :global(.swagger-ui .info) {
		margin: 16px 0;
	}
	.swagger-viewer :global(.swagger-ui .scheme-container) {
		display: none;
	}
</style>
