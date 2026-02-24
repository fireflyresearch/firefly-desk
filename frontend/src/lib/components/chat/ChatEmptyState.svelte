<!--
  ChatEmptyState.svelte - Welcome screen shown when no messages exist.

  Displays a personalized greeting from Ember with an animated hero section
  and a 2x3 grid of glassmorphism suggestion chips with staggered entrance
  animation.  Suggestions are role-aware: admins and operators see tailored
  prompts.  Dynamic subtitle shows system/knowledge-doc counts fetched from
  the dashboard stats API.

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
		ListChecks,
		GitBranch,
		Zap
	} from 'lucide-svelte';
	import { currentUser } from '$lib/stores/user.js';
	import { apiJson } from '$lib/services/api.js';
	import EmberAvatar from './EmberAvatar.svelte';

	interface ChatEmptyStateProps {
		onSuggestionClick: (text: string) => void;
	}

	let { onSuggestionClick }: ChatEmptyStateProps = $props();

	// -----------------------------------------------------------------------
	// Icon name → Lucide component mapping
	// -----------------------------------------------------------------------

	type LucideIcon = typeof Search;

	const iconMap: Record<string, LucideIcon> = {
		'search': Search,
		'activity': Activity,
		'book-open': BookOpen,
		'shield': Shield,
		'database': Database,
		'help-circle': HelpCircle,
		'heart-pulse': HeartPulse,
		'settings': Settings,
		'cpu': Cpu,
		'list-checks': ListChecks,
		'git-branch': GitBranch,
		'zap': Zap,
	};

	// -----------------------------------------------------------------------
	// Dynamic counts, suggestions & animation state
	// -----------------------------------------------------------------------

	interface APISuggestion {
		icon: string;
		title: string;
		description: string;
		text: string;
	}

	interface Suggestion {
		icon: LucideIcon;
		title: string;
		description: string;
		text: string;
	}

	let systemCount = $state(0);
	let docCount = $state(0);
	let mounted = $state(false);
	let apiSuggestions = $state<Suggestion[]>([]);

	$effect(() => {
		(async () => {
			// Fetch dashboard stats and suggestions in parallel
			const [statsResult, suggestionsResult] = await Promise.allSettled([
				apiJson<{ system_count?: number; knowledge_doc_count?: number }>('/admin/dashboard/stats'),
				apiJson<{ suggestions: APISuggestion[] }>('/chat/suggestions'),
			]);

			if (statsResult.status === 'fulfilled') {
				systemCount = statsResult.value.system_count ?? 0;
				docCount = statsResult.value.knowledge_doc_count ?? 0;
			}

			if (suggestionsResult.status === 'fulfilled') {
				apiSuggestions = suggestionsResult.value.suggestions.map((s) => ({
					icon: iconMap[s.icon] ?? HelpCircle,
					title: s.title,
					description: s.description,
					text: s.text,
				}));
			}

			setTimeout(() => {
				mounted = true;
			}, 100);
		})();
	});

	// -----------------------------------------------------------------------
	// Personalised greeting
	// -----------------------------------------------------------------------

	let firstName = $derived($currentUser?.displayName?.split(' ')[0] ?? null);

	let greeting = $derived(
		firstName ? `Hello ${firstName}, I'm Ember` : `Hello, I'm Ember`
	);

	let subtitle = $derived.by(() => {
		const parts: string[] = [];
		if (systemCount > 0) parts.push(`${systemCount} system${systemCount !== 1 ? 's' : ''}`);
		if (docCount > 0) parts.push(`${docCount} knowledge document${docCount !== 1 ? 's' : ''}`);
		return parts.length > 0
			? `I have access to ${parts.join(' and ')}. How can I help?`
			: 'Ready to help you explore and manage your infrastructure';
	});

	// -----------------------------------------------------------------------
	// Suggestions: use API response, fall back to static defaults
	// -----------------------------------------------------------------------

	const fallbackSuggestions: Suggestion[] = [
		{ icon: Search, title: 'Explore Systems', description: 'View all registered systems and services', text: 'Show me all registered systems' },
		{ icon: BookOpen, title: 'Knowledge Base', description: 'Search organizational knowledge', text: 'What information is available in the knowledge base?' },
		{ icon: HelpCircle, title: 'Capabilities', description: 'Learn what I can do for you', text: 'What can you help me with?' },
	];

	let suggestions = $derived(apiSuggestions.length > 0 ? apiSuggestions : fallbackSuggestions);
</script>

<div
	class="relative flex min-h-full flex-col items-center justify-center px-4"
	style="background: radial-gradient(circle at 50% 30%, var(--color-ember-glow) 0%, transparent 60%)"
>
	<!-- Hero section -->
	<div class="mb-10 flex flex-col items-center gap-4">
		<!-- Avatar with animated radial glow ring -->
		<div class="relative">
			<!-- Outer pulsing glow -->
			<div
				class="absolute inset-0 -m-4 rounded-full blur-xl"
				style="background: radial-gradient(circle, var(--color-ember) 0%, transparent 70%); opacity: 0.12; animation: ember-pulse 3s ease-in-out infinite;"
			></div>
			<!-- Inner glow ring -->
			<div
				class="absolute inset-0 -m-2 rounded-full border border-ember/20"
				style="box-shadow: 0 0 20px var(--color-ember-glow), inset 0 0 20px var(--color-ember-glow);"
			></div>
			<!-- Avatar container -->
			<div
				class="relative flex h-16 w-16 items-center justify-center rounded-full border border-ember/20 bg-surface-elevated shadow-lg"
			>
				<EmberAvatar size={36} />
			</div>
		</div>

		<!-- Greeting text -->
		<div class="text-center">
			<h2 class="text-2xl font-bold text-text-primary">
				{greeting}
			</h2>
			<p class="mt-2 text-sm text-text-secondary">
				{subtitle}
			</p>
		</div>
	</div>

	<!-- Suggestion chips - 2x3 grid with staggered entrance -->
	<div class="grid w-full max-w-2xl grid-cols-2 gap-3">
		{#each suggestions as suggestion, i}
			<button
				type="button"
				class="group flex items-start gap-3 rounded-xl border border-border/50 bg-surface-secondary/60 px-4 py-3.5 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-ember/30 hover:bg-surface-secondary/80 hover:shadow-lg hover:shadow-ember/5
					{mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}"
				style="transition-delay: {mounted ? i * 80 : 0}ms"
				onclick={() => onSuggestionClick(suggestion.text)}
			>
				<span
					class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember transition-colors group-hover:bg-ember/20"
				>
					<suggestion.icon size={16} />
				</span>
				<div class="min-w-0">
					<div class="text-sm font-medium text-text-primary">
						{suggestion.title}
					</div>
					<div class="mt-0.5 text-xs text-text-secondary">
						{suggestion.description}
					</div>
				</div>
			</button>
		{/each}
	</div>
</div>

<style>
	@keyframes ember-pulse {
		0%,
		100% {
			opacity: 0.1;
			transform: scale(1);
		}
		50% {
			opacity: 0.18;
			transform: scale(1.08);
		}
	}
</style>
