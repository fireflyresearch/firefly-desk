<!--
  MarkdownContent.svelte - Renders markdown content as sanitized HTML.

  Uses `marked` for markdown parsing and `DOMPurify` for XSS protection.
  Styled with Tailwind Typography for consistent, theme-aware rendering.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	interface MarkdownContentProps {
		content: string;
	}

	let { content }: MarkdownContentProps = $props();
	let html = $derived(DOMPurify.sanitize(marked.parse(content) as string));
</script>

<div class="prose prose-sm max-w-none text-text-primary">{@html html}</div>
