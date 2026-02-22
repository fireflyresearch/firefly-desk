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
		ListChecks
	} from 'lucide-svelte';
	import { currentUser } from '$lib/stores/user.js';
	import { apiJson } from '$lib/services/api.js';
	import EmberAvatar from './EmberAvatar.svelte';

	interface ChatEmptyStateProps {
		onSuggestionClick: (text: string) => void;
	}

	let { onSuggestionClick }: ChatEmptyStateProps = $props();

	// -----------------------------------------------------------------------
	// Dynamic counts & animation state
	// -----------------------------------------------------------------------

	let systemCount = $state(0);
	let docCount = $state(0);
	let mounted = $state(false);

	$effect(() => {
		(async () => {
			try {
				const stats = await apiJson<{
					system_count?: number;
					knowledge_doc_count?: number;
				}>('/dashboard/stats');
				systemCount = stats.system_count ?? 0;
				docCount = stats.knowledge_doc_count ?? 0;
			} catch {
				// Dashboard stats may not be available yet -- that is fine.
			}
			// Stagger animation trigger after a brief delay so the layout paints first
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
	// Role-based suggestion sets (title + description for two-line layout)
	// -----------------------------------------------------------------------

	/** Use a concrete Lucide icon type to avoid Component<{}> vs Component<IconProps> mismatch. */
	type LucideIcon = typeof Search;

	interface Suggestion {
		icon: LucideIcon;
		title: string;
		description: string;
		text: string;
	}

	const adminSuggestions: Suggestion[] = [
		{
			icon: HeartPulse,
			title: 'System Health',
			description: 'Review current status of all systems',
			text: 'Review system health'
		},
		{
			icon: Shield,
			title: 'Audit Events',
			description: 'Check recent security and activity logs',
			text: 'Check recent audit events'
		},
		{
			icon: Settings,
			title: 'LLM Configuration',
			description: 'Manage AI model providers',
			text: 'Manage LLM providers'
		},
		{
			icon: Activity,
			title: 'Active Sessions',
			description: 'Monitor current agent activity',
			text: 'Show active agent sessions'
		},
		{
			icon: Cpu,
			title: 'Resources',
			description: 'Check running resources and usage',
			text: 'What resources are running?'
		},
		{
			icon: HelpCircle,
			title: 'Capabilities',
			description: 'Learn what I can do for you',
			text: 'What can you help me with?'
		}
	];

	const operatorSuggestions: Suggestion[] = [
		{
			icon: Search,
			title: 'Explore Systems',
			description: 'View all registered systems and services',
			text: 'Show me all registered systems'
		},
		{
			icon: Activity,
			title: 'Service Status',
			description: 'Check health of a specific service',
			text: 'What is the status of the payment service?'
		},
		{
			icon: ListChecks,
			title: 'Endpoints',
			description: 'List available service endpoints',
			text: 'List available endpoints'
		},
		{
			icon: Database,
			title: 'Deployments',
			description: 'Review recent deployment activity',
			text: 'Show recent deployments'
		},
		{
			icon: BookOpen,
			title: 'Knowledge Base',
			description: 'Search organizational knowledge',
			text: 'How does the knowledge base work?'
		},
		{
			icon: HelpCircle,
			title: 'Get Help',
			description: 'Learn what I can do for you',
			text: 'What can you help me with?'
		}
	];

	const defaultSuggestions: Suggestion[] = [
		{
			icon: Search,
			title: 'Explore Systems',
			description: 'View all registered systems and services',
			text: 'Show me all registered systems'
		},
		{
			icon: Activity,
			title: 'Service Status',
			description: 'Check the health of your services',
			text: 'What is the status of all services?'
		},
		{
			icon: BookOpen,
			title: 'Knowledge Base',
			description: 'Search organizational knowledge',
			text: 'How does the knowledge base work?'
		},
		{
			icon: Shield,
			title: 'Audit Logs',
			description: 'Review recent audit events',
			text: 'Review recent audit events'
		},
		{
			icon: Database,
			title: 'Endpoints',
			description: 'List available service endpoints',
			text: 'List available service endpoints'
		},
		{
			icon: HelpCircle,
			title: 'Get Help',
			description: 'Learn what I can do for you',
			text: 'What can you help me with?'
		}
	];

	let suggestions = $derived.by(() => {
		const roles = $currentUser?.roles ?? [];
		if (roles.includes('admin')) return adminSuggestions;
		if (roles.includes('operator')) return operatorSuggestions;
		return defaultSuggestions;
	});
</script>

<div
	class="relative flex h-full flex-col items-center justify-center px-4"
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
