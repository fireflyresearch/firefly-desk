<!--
  SwaggerViewer.svelte - Renders an OpenAPI spec using Swagger UI.

  Dynamically imports swagger-ui-bundle to avoid SSR issues and renders
  a read-only API documentation view.

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

	onMount(async () => {
		if (!containerEl) return;

		try {
			// Parse spec (could be JSON or YAML-ish)
			let specObj: object;
			try {
				specObj = JSON.parse(spec);
			} catch {
				// If not valid JSON, try displaying as-is
				error = 'Could not parse OpenAPI spec as JSON. Raw content shown below.';
				loading = false;
				return;
			}

			// Dynamically import swagger-ui to avoid SSR issues
			// @ts-ignore -- swagger-ui-dist has no type declarations
			const { default: SwaggerUIBundle } = await import('swagger-ui-dist/swagger-ui-bundle.js');

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
