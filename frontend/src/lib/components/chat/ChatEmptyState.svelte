<!--
  ChatEmptyState.svelte - Welcome screen shown when no messages exist.

  Displays a personalized greeting from Ember with a 2x3 grid of clickable
  suggestion chips that seed the first conversation.  Suggestions are
  role-aware: admins and operators see tailored prompts.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Activity,
		BookOpen,
		Shield,
		Database,
		HelpCircle,
		HeartPulse,
		Settings,
		Cpu,
		ListChecks
	} from 'lucide-svelte';
	import type { Component } from 'svelte';
	import { currentUser } from '$lib/stores/user.js';
	import EmberAvatar from './EmberAvatar.svelte';

	interface ChatEmptyStateProps {
		onSuggestionClick: (text: string) => void;
	}

	let { onSuggestionClick }: ChatEmptyStateProps = $props();

	// -----------------------------------------------------------------------
	// Personalised greeting
	// -----------------------------------------------------------------------

	let firstName = $derived(
		$currentUser?.displayName?.split(' ')[0] ?? null
	);

	let greeting = $derived(
		firstName
			? `Hello ${firstName}, I am Ember. How can I help you today?`
			: 'Hello, I am Ember. How can I help you today?'
	);

	// -----------------------------------------------------------------------
	// Role-based suggestion sets
	// -----------------------------------------------------------------------

	const adminSuggestions: { icon: Component; text: string }[] = [
		{ icon: HeartPulse, text: 'Review system health' },
		{ icon: Shield, text: 'Check recent audit events' },
		{ icon: Settings, text: 'Manage LLM providers' },
		{ icon: Activity, text: 'Show active agent sessions' },
		{ icon: Cpu, text: 'What resources are running?' },
		{ icon: HelpCircle, text: 'What can you help me with?' }
	];

	const operatorSuggestions: { icon: Component; text: string }[] = [
		{ icon: Search, text: 'Show me all registered systems' },
		{ icon: Activity, text: 'What is the status of the payment service?' },
		{ icon: ListChecks, text: 'List available endpoints' },
		{ icon: Database, text: 'Show recent deployments' },
		{ icon: BookOpen, text: 'How does the knowledge base work?' },
		{ icon: HelpCircle, text: 'What can you help me with?' }
	];

	const defaultSuggestions: { icon: Component; text: string }[] = [
		{ icon: Search, text: 'Show me all registered systems' },
		{ icon: Activity, text: 'What is the status of the payment service?' },
		{ icon: BookOpen, text: 'How does the knowledge base work?' },
		{ icon: Shield, text: 'Review recent audit events' },
		{ icon: Database, text: 'List available service endpoints' },
		{ icon: HelpCircle, text: 'What can you help me with?' }
	];

	let suggestions = $derived.by(() => {
		const roles = $currentUser?.roles ?? [];
		if (roles.includes('admin')) return adminSuggestions;
		if (roles.includes('operator')) return operatorSuggestions;
		return defaultSuggestions;
	});
</script>

<div class="flex h-full flex-col items-center justify-center gap-8 px-4">
	<!-- Greeting -->
	<div class="flex flex-col items-center gap-3">
		<div
			class="flex h-14 w-14 items-center justify-center rounded-full bg-accent/10"
		>
			<EmberAvatar size={28} />
		</div>
		<h2 class="text-lg font-semibold text-text-primary">
			{greeting}
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
