<!--
  MarkdownContent.svelte — Renders Markdown as sanitized HTML
  with Tailwind Typography prose styling. For read-only display.

  A lightweight alternative to RichEditor for pure read-only rendering.
  Uses marked (instead of Tiptap) with DOMPurify for sanitization.
  All imports are dynamic for SSR safety in SvelteKit.

  Props:
    content   - Markdown string to render
    maxHeight - Optional CSS max-height (enables overflow-y-auto)

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		content: string;
		maxHeight?: string;
	}

	let { content, maxHeight = '' }: Props = $props();
	let html = $state('');
	let renderContent: ((text: string) => Promise<void>) | null = null;

	onMount(async () => {
		const { marked } = await import('marked');
		const DOMPurify = (await import('dompurify')).default;
		renderContent = async (text: string) => {
			html = DOMPurify.sanitize(await marked.parse(text || ''));
		};
		await renderContent(content);
	});

	$effect(() => {
		if (renderContent && content !== undefined) {
			renderContent(content);
		}
	});
</script>

<div
	class="prose prose-sm max-w-none dark:prose-invert text-text-primary"
	class:overflow-y-auto={!!maxHeight}
	style:max-height={maxHeight || undefined}
>
	{@html html}
</div>
