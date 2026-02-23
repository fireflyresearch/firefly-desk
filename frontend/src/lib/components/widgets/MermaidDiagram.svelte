<!--
  MermaidDiagram.svelte - Renders Mermaid diagrams with lazy-loaded library.

  Lazy-loads the mermaid library on first render. Detects dark/light theme
  and passes it to mermaid's init. Shows an error boundary with raw code
  fallback for invalid syntax. SVG output is sanitized with DOMPurify.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { AlertTriangle } from 'lucide-svelte';
	import DOMPurify from 'dompurify';

	interface MermaidDiagramProps {
		code: string;
		title?: string;
	}

	let { code, title }: MermaidDiagramProps = $props();

	let container: HTMLDivElement;
	let error = $state<string | null>(null);
	let loading = $state(true);

	/** Generate a unique ID for each render to avoid mermaid ID collisions. */
	let diagramId = $derived(`mermaid-${crypto.randomUUID().slice(0, 8)}`);

	$effect(() => {
		if (!container) return;

		error = null;
		loading = true;

		let cancelled = false;

		(async () => {
			try {
				const mermaid = (await import('mermaid')).default;

				const isDark = document.documentElement.classList.contains('dark');

				mermaid.initialize({
					startOnLoad: false,
					theme: isDark ? 'dark' : 'default',
					securityLevel: 'strict',
					fontFamily: "'Plus Jakarta Sans Variable', system-ui, sans-serif"
				});

				const { svg } = await mermaid.render(diagramId, code);

				if (!cancelled) {
					// Sanitize SVG output before inserting into the DOM
					const sanitized = DOMPurify.sanitize(svg, {
						USE_PROFILES: { svg: true, svgFilters: true },
						ADD_TAGS: ['foreignObject']
					});
					container.replaceChildren();
					const template = document.createElement('template');
					template.innerHTML = sanitized;
					container.appendChild(template.content);
					loading = false;
				}
			} catch (err) {
				if (!cancelled) {
					error = err instanceof Error ? err.message : 'Failed to render diagram';
					loading = false;
				}
			}
		})();

		return () => {
			cancelled = true;
		};
	});
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	{#if title}
		<div class="border-b border-border px-5 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="p-4">
		{#if loading}
			<div class="flex items-center justify-center py-8">
				<div class="mermaid-spinner h-6 w-6 rounded-full border-2 border-border border-t-accent"></div>
				<span class="ml-2 text-xs text-text-secondary">Loading diagram...</span>
			</div>
		{/if}

		{#if error}
			<div class="rounded-lg border border-danger/20 bg-danger/5 p-4">
				<div class="flex items-start gap-2">
					<span class="mt-0.5 shrink-0 text-danger">
						<AlertTriangle size={16} />
					</span>
					<div class="min-w-0">
						<p class="text-xs font-medium text-danger">Diagram render error</p>
						<p class="mt-1 text-xs text-text-secondary">{error}</p>
					</div>
				</div>
				<!-- Fallback: show raw code -->
				<pre class="mt-3 overflow-x-auto rounded-md bg-surface-secondary p-3 text-xs text-text-secondary font-mono">{code}</pre>
			</div>
		{/if}

		<div bind:this={container} class="mermaid-container flex justify-center {loading || error ? 'hidden' : ''}"></div>
	</div>
</div>

<style>
	@keyframes mermaid-spin {
		to { transform: rotate(360deg); }
	}

	.mermaid-spinner {
		animation: mermaid-spin 0.8s linear infinite;
	}

	.mermaid-container :global(svg) {
		max-width: 100%;
		height: auto;
	}
</style>
