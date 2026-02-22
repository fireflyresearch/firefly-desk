<!--
  ChatEmptyState.svelte - Welcome screen shown when no messages exist.

  Displays a friendly greeting from Ember with a 2x3 grid of clickable
  suggestion chips that seed the first conversation.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Bot,
		Search,
		Activity,
		BookOpen,
		Shield,
		Database,
		HelpCircle
	} from 'lucide-svelte';
	import type { Component } from 'svelte';

	interface ChatEmptyStateProps {
		onSuggestionClick: (text: string) => void;
	}

	let { onSuggestionClick }: ChatEmptyStateProps = $props();

	const suggestions: { icon: Component; text: string }[] = [
		{ icon: Search, text: 'Show me all registered systems' },
		{ icon: Activity, text: 'What is the status of the payment service?' },
		{ icon: BookOpen, text: 'How does the knowledge base work?' },
		{ icon: Shield, text: 'Review recent audit events' },
		{ icon: Database, text: 'List available service endpoints' },
		{ icon: HelpCircle, text: 'What can you help me with?' }
	];
</script>

<div class="flex h-full flex-col items-center justify-center gap-8 px-4">
	<!-- Greeting -->
	<div class="flex flex-col items-center gap-3">
		<div
			class="flex h-14 w-14 items-center justify-center rounded-full bg-accent/10 text-accent"
		>
			<Bot size={28} strokeWidth={1.5} />
		</div>
		<h2 class="text-lg font-semibold text-text-primary">
			Hello, I am Ember. How can I help you today?
		</h2>
	</div>

	<!-- Suggestion chips - 2x3 grid -->
	<div class="grid w-full max-w-xl grid-cols-2 gap-3">
		{#each suggestions as suggestion}
			<button
				type="button"
				class="flex items-center gap-3 rounded-xl border border-border bg-surface-secondary px-4 py-3 text-left text-sm text-text-primary transition-colors hover:border-accent/40 hover:bg-surface-hover"
				onclick={() => onSuggestionClick(suggestion.text)}
			>
				<span class="shrink-0 text-accent">
					<suggestion.icon size={18} />
				</span>
				<span>{suggestion.text}</span>
			</button>
		{/each}
	</div>
</div>
