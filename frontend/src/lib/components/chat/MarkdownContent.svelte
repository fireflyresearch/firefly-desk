<!--
  MarkdownContent.svelte - Renders markdown content as sanitized HTML with
  syntax highlighting and interactive code blocks.

  Uses `marked` for markdown parsing, `marked-highlight` + `highlight.js` for
  syntax highlighting, and `DOMPurify` for XSS protection. Code blocks get a
  copy-to-clipboard button that appears on hover.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { marked } from 'marked';
	import { markedHighlight } from 'marked-highlight';
	import DOMPurify from 'dompurify';
	import hljs from 'highlight.js/lib/core';

	// Register language subsets (tree-shakeable)
	import python from 'highlight.js/lib/languages/python';
	import javascript from 'highlight.js/lib/languages/javascript';
	import typescript from 'highlight.js/lib/languages/typescript';
	import json from 'highlight.js/lib/languages/json';
	import bash from 'highlight.js/lib/languages/bash';
	import sql from 'highlight.js/lib/languages/sql';
	import yaml from 'highlight.js/lib/languages/yaml';
	import xml from 'highlight.js/lib/languages/xml';
	import css from 'highlight.js/lib/languages/css';

	import 'highlight.js/styles/github-dark-dimmed.css';
	import ImageLightbox from './ImageLightbox.svelte';

	hljs.registerLanguage('python', python);
	hljs.registerLanguage('javascript', javascript);
	hljs.registerLanguage('typescript', typescript);
	hljs.registerLanguage('json', json);
	hljs.registerLanguage('bash', bash);
	hljs.registerLanguage('shell', bash);
	hljs.registerLanguage('sql', sql);
	hljs.registerLanguage('yaml', yaml);
	hljs.registerLanguage('yml', yaml);
	hljs.registerLanguage('xml', xml);
	hljs.registerLanguage('html', xml);
	hljs.registerLanguage('css', css);

	// Configure marked with highlight.js integration
	marked.use(
		markedHighlight({
			langPrefix: 'hljs language-',
			highlight(code: string, lang: string): string {
				if (lang && hljs.getLanguage(lang)) {
					return hljs.highlight(code, { language: lang }).value;
				}
				// Auto-detect for unlabeled code blocks
				return hljs.highlightAuto(code).value;
			}
		})
	);

	// Configure DOMPurify to allow highlight.js class attributes on spans/code only
	const purifyConfig = {
		ADD_TAGS: ['span'] as string[]
	};

	// Restrict class attribute to only span and code elements (for highlight.js tokens)
	DOMPurify.addHook('afterSanitizeAttributes', (node) => {
		if (
			node.hasAttribute('class') &&
			node.nodeName !== 'SPAN' &&
			node.nodeName !== 'CODE' &&
			node.nodeName !== 'PRE'
		) {
			node.removeAttribute('class');
		}
	});

	const clipboardIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;

	interface MarkdownContentProps {
		content: string;
	}

	let { content }: MarkdownContentProps = $props();
	let container: HTMLDivElement;
	let lightboxSrc = $state('');
	let lightboxAlt = $state('');

	// Parse markdown and sanitize with DOMPurify (XSS protection preserved)
	let html = $derived(DOMPurify.sanitize(marked.parse(content) as string, purifyConfig));

	// Helper: create a clipboard icon element
	function createCopyIcon(): HTMLSpanElement {
		const iconWrapper = document.createElement('span');
		iconWrapper.className = 'copy-icon';
		DOMPurify.sanitize(clipboardIcon, { RETURN_DOM_FRAGMENT: true })
			.childNodes.forEach((node) => iconWrapper.appendChild(node.cloneNode(true)));
		return iconWrapper;
	}

	// After HTML renders, add copy buttons to all code blocks
	$effect(() => {
		html; // track so this re-runs when content changes

		if (!container) return;

		const timeouts: ReturnType<typeof setTimeout>[] = [];

		const pres = container.querySelectorAll('pre');
		pres.forEach((pre) => {
			if (pre.querySelector('.copy-btn')) return;

			const btn = document.createElement('button');
			btn.className = 'copy-btn';
			btn.appendChild(createCopyIcon());
			btn.title = 'Copy code';

			let copyTimer: ReturnType<typeof setTimeout> | null = null;

			btn.addEventListener('click', async () => {
				if (copyTimer) clearTimeout(copyTimer);
				const code = pre.querySelector('code')?.textContent ?? '';
				try {
					await navigator.clipboard.writeText(code);
					btn.textContent = 'Copied!';
				} catch {
					btn.textContent = 'Failed';
				}
				copyTimer = setTimeout(() => {
					copyTimer = null;
					btn.textContent = '';
					btn.appendChild(createCopyIcon());
				}, 2000);
				timeouts.push(copyTimer);
			});

			pre.appendChild(btn);
		});

		// Make images clickable for lightbox
		const imgs = container.querySelectorAll('img');
		imgs.forEach((img) => {
			if (img.dataset.lightboxReady) return;
			img.dataset.lightboxReady = 'true';
			img.style.cursor = 'pointer';
			img.addEventListener('click', () => {
				lightboxSrc = img.src;
				lightboxAlt = img.alt || img.src.split('/').pop() || 'Image';
			});
		});

		return () => {
			timeouts.forEach(clearTimeout);
		};
	});
</script>

<div class="markdown-content prose prose-sm max-w-none text-text-primary" bind:this={container}>
	{@html html}
</div>

{#if lightboxSrc}
	<ImageLightbox src={lightboxSrc} alt={lightboxAlt} onclose={() => { lightboxSrc = ''; }} />
{/if}

<style>
	/* Code blocks */
	.markdown-content :global(pre) {
		position: relative;
		border-radius: 0.75rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface-secondary);
		overflow-x: auto;
	}

	.markdown-content :global(pre code) {
		font-family: 'JetBrains Mono', monospace;
		font-size: 0.8125rem;
		line-height: 1.6;
	}

	/* Inline code */
	.markdown-content :global(code:not(pre code)) {
		background: var(--color-surface-secondary);
		border-radius: 0.25rem;
		padding: 0.125rem 0.375rem;
		font-size: 0.875em;
		font-family: 'JetBrains Mono', monospace;
	}

	/* Tables */
	.markdown-content :global(table) {
		border-collapse: collapse;
		width: 100%;
	}

	.markdown-content :global(th),
	.markdown-content :global(td) {
		border: 1px solid var(--color-border);
		padding: 0.5rem 0.75rem;
		text-align: left;
	}

	.markdown-content :global(tr:nth-child(even)) {
		background: var(--color-surface-secondary);
	}

	/* Blockquotes */
	.markdown-content :global(blockquote) {
		border-left: 3px solid var(--color-ember);
		padding-left: 1rem;
		color: var(--color-text-secondary);
		font-style: italic;
	}

	/* Links */
	.markdown-content :global(a) {
		color: var(--color-accent);
		text-decoration: none;
	}

	.markdown-content :global(a:hover) {
		text-decoration: underline;
	}

	/* Horizontal rules */
	.markdown-content :global(hr) {
		border: none;
		height: 1px;
		background: linear-gradient(to right, transparent, var(--color-border), transparent);
	}

	/* Images */
	.markdown-content :global(img) {
		border-radius: 0.5rem;
		box-shadow: 0 1px 3px rgb(0 0 0 / 0.1);
		max-width: 100%;
		height: auto;
		cursor: pointer;
		transition: box-shadow 150ms ease, transform 150ms ease;
	}

	.markdown-content :global(img:hover) {
		box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
		transform: scale(1.01);
	}

	/* Copy button */
	.markdown-content :global(.copy-btn) {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		padding: 0.25rem 0.5rem;
		border-radius: 0.375rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface-elevated);
		color: var(--color-text-secondary);
		font-size: 0.75rem;
		cursor: pointer;
		opacity: 0;
		transition: opacity 150ms ease;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.markdown-content :global(pre:hover .copy-btn) {
		opacity: 1;
	}

	.markdown-content :global(.copy-btn:hover) {
		background: var(--color-surface-hover);
		color: var(--color-text-primary);
	}
</style>
