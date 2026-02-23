<!--
  CodeBlock.svelte - Enhanced code display with syntax highlighting.

  Renders a code block with highlight.js syntax highlighting, an optional
  title bar, a language label, toggleable line numbers, a copy-to-clipboard
  button with checkmark feedback, and a scrollable container with max-height
  for long code blocks.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Copy, Check } from 'lucide-svelte';
	import hljs from 'highlight.js/lib/core';

	import python from 'highlight.js/lib/languages/python';
	import javascript from 'highlight.js/lib/languages/javascript';
	import typescript from 'highlight.js/lib/languages/typescript';
	import json from 'highlight.js/lib/languages/json';
	import bash from 'highlight.js/lib/languages/bash';
	import sql from 'highlight.js/lib/languages/sql';
	import yaml from 'highlight.js/lib/languages/yaml';
	import xml from 'highlight.js/lib/languages/xml';
	import css from 'highlight.js/lib/languages/css';

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

	interface CodeBlockProps {
		code: string;
		language?: string;
		title?: string;
		showLineNumbers?: boolean;
	}

	let { code, language, title, showLineNumbers = true }: CodeBlockProps = $props();

	let copied = $state(false);
	let copyTimer: ReturnType<typeof setTimeout> | null = null;

	/** Highlighted HTML for the code. */
	let highlighted = $derived.by(() => {
		if (language && hljs.getLanguage(language)) {
			return hljs.highlight(code, { language }).value;
		}
		return hljs.highlightAuto(code).value;
	});

	/** Code split into lines for line-number rendering. */
	let lines = $derived(highlighted.split('\n'));

	/** Resolved language label (detection fallback). */
	let languageLabel = $derived.by(() => {
		if (language) return language;
		if (!language) {
			const result = hljs.highlightAuto(code);
			return result.language ?? 'text';
		}
		return 'text';
	});

	async function handleCopy() {
		if (copyTimer) clearTimeout(copyTimer);
		try {
			await navigator.clipboard.writeText(code);
			copied = true;
		} catch {
			// Clipboard API not available (e.g. insecure context)
			copied = false;
		}
		copyTimer = setTimeout(() => {
			copied = false;
			copyTimer = null;
		}, 2000);
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	<!-- Title bar / header -->
	<div class="flex items-center justify-between border-b border-border bg-surface-secondary/50 px-4 py-2">
		<div class="flex items-center gap-2 min-w-0">
			{#if title}
				<span class="truncate text-sm font-semibold text-text-primary">{title}</span>
			{/if}
		</div>
		<div class="flex items-center gap-2 shrink-0">
			<span class="rounded-md bg-surface-hover px-2 py-0.5 text-xs font-medium text-text-secondary">
				{languageLabel}
			</span>
			<button
				type="button"
				class="inline-flex items-center gap-1 rounded-md border border-border bg-surface-elevated px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				title={copied ? 'Copied!' : 'Copy code'}
				onclick={handleCopy}
			>
				{#if copied}
					<Check size={12} class="text-success" />
					<span class="text-success">Copied</span>
				{:else}
					<Copy size={12} />
					<span>Copy</span>
				{/if}
			</button>
		</div>
	</div>

	<!-- Code area -->
	<div class="codeblock-scroll overflow-auto">
		<table class="w-full border-collapse" role="presentation">
			<tbody>
				{#each lines as line, i}
					<tr>
						{#if showLineNumbers}
							<td
								class="sticky left-0 select-none border-r border-border/50 bg-surface-secondary/30 px-3 py-0 text-right align-top font-mono text-xs text-text-secondary/50 leading-relaxed"
								aria-hidden="true"
							>
								{i + 1}
							</td>
						{/if}
						<td class="px-4 py-0 align-top">
							<code class="font-mono text-[0.8125rem] leading-relaxed text-text-primary">
								{@html line || '&nbsp;'}
							</code>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.codeblock-scroll {
		max-height: 28rem;
	}

	/* Import highlight.js theme inline so it respects the widget scope */
	:global(.hljs-keyword) { color: var(--color-accent, #7c3aed); }
	:global(.hljs-string) { color: var(--color-success, #16a34a); }
	:global(.hljs-number) { color: var(--color-ember, #f59e0b); }
	:global(.hljs-comment) { color: var(--color-text-secondary, #6b7280); font-style: italic; }
	:global(.hljs-built_in) { color: var(--color-accent, #7c3aed); }
	:global(.hljs-function) { color: var(--color-info, #3b82f6); }
	:global(.hljs-title) { color: var(--color-info, #3b82f6); }
	:global(.hljs-params) { color: var(--color-text-primary, #e5e7eb); }
	:global(.hljs-attr) { color: var(--color-ember, #f59e0b); }
	:global(.hljs-literal) { color: var(--color-danger, #ef4444); }
	:global(.hljs-type) { color: var(--color-ember, #f59e0b); }
	:global(.hljs-meta) { color: var(--color-text-secondary, #6b7280); }
	:global(.hljs-punctuation) { color: var(--color-text-secondary, #6b7280); }
</style>
