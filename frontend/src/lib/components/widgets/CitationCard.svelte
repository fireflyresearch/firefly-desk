<!--
  CitationCard.svelte - Knowledge citation card with source, snippet, and relevance score.

  Renders a compact reference card for knowledge-base citations. Shows the
  source title prominently, a snippet of the relevant text, an optional
  relevance score badge, and an optional link to the source document.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { BookOpen, ExternalLink } from 'lucide-svelte';

	interface CitationCardProps {
		source_title: string;
		snippet: string;
		score?: number;
		document_id?: string;
		source_url?: string;
	}

	let { source_title, snippet, score, document_id, source_url }: CitationCardProps = $props();

	/** Format score as a percentage string. */
	let scoreLabel = $derived(score != null ? `${Math.round(score * 100)}%` : null);

	/** Color the score badge based on relevance. */
	let scoreBadgeClass = $derived.by(() => {
		if (score == null) return '';
		if (score >= 0.8) return 'bg-success/15 text-success';
		if (score >= 0.5) return 'bg-ember/15 text-ember';
		return 'bg-text-secondary/15 text-text-secondary';
	});
</script>

<div class="rounded-xl border border-border border-l-4 border-l-accent bg-surface-elevated p-4 shadow-sm transition-shadow hover:shadow-md">
	<!-- Header: icon + title + score -->
	<div class="flex items-start justify-between gap-3">
		<div class="flex items-center gap-2 min-w-0">
			<span class="shrink-0 text-accent">
				<BookOpen size={16} />
			</span>
			{#if source_url}
				<a
					href={source_url}
					target="_blank"
					rel="noopener noreferrer"
					class="truncate text-sm font-semibold text-text-primary hover:text-accent transition-colors"
				>
					{source_title}
					<ExternalLink size={12} class="ml-1 inline-block align-text-top" />
				</a>
			{:else}
				<h3 class="truncate text-sm font-semibold text-text-primary">{source_title}</h3>
			{/if}
		</div>

		{#if scoreLabel}
			<span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold {scoreBadgeClass}">
				{scoreLabel}
			</span>
		{/if}
	</div>

	<!-- Snippet -->
	<p class="mt-2 line-clamp-3 text-sm text-text-secondary leading-relaxed">
		{snippet}
	</p>

	<!-- Document ID (subtle footer) -->
	{#if document_id}
		<p class="mt-2 text-xs text-text-secondary/60 font-mono truncate">
			{document_id}
		</p>
	{/if}
</div>
