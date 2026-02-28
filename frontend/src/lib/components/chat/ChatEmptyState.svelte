<!--
  ChatEmptyState.svelte - Welcome screen shown when no messages exist.

  Displays a personalized, time-aware greeting from Ember with an animated
  hero section, contextual user info, resource stats bar, and a responsive
  grid of smart suggestion cards with staggered entrance animation.
  Suggestions are role-aware: admins and operators see tailored prompts.
  Greeting language adapts to the user's agentLanguage setting.

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
		Zap,
		FileText,
		Layers,
		Server,
		MessageSquare
	} from 'lucide-svelte';
	import { currentUser, isAdmin } from '$lib/stores/user.js';
	import { userSettings } from '$lib/stores/settings.js';
	import { apiJson } from '$lib/services/api.js';
	import EmberAvatar from './EmberAvatar.svelte';

	interface ChatEmptyStateProps {
		onSuggestionClick: (text: string) => void;
	}

	let { onSuggestionClick }: ChatEmptyStateProps = $props();

	// -----------------------------------------------------------------------
	// Icon name -> Lucide component mapping
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
	// Time-of-day greeting with multilingual support
	// -----------------------------------------------------------------------

	type TimePeriod = 'morning' | 'afternoon' | 'evening' | 'night';

	const greetings: Record<string, Record<TimePeriod, string>> = {
		en: { morning: 'Good morning', afternoon: 'Good afternoon', evening: 'Good evening', night: 'Good night' },
		es: { morning: 'Buenos dias', afternoon: 'Buenas tardes', evening: 'Buenas tardes', night: 'Buenas noches' },
		fr: { morning: 'Bonjour', afternoon: 'Bon apres-midi', evening: 'Bonsoir', night: 'Bonne nuit' },
		pt: { morning: 'Bom dia', afternoon: 'Boa tarde', evening: 'Boa noite', night: 'Boa noite' },
		de: { morning: 'Guten Morgen', afternoon: 'Guten Tag', evening: 'Guten Abend', night: 'Gute Nacht' },
		it: { morning: 'Buongiorno', afternoon: 'Buon pomeriggio', evening: 'Buonasera', night: 'Buonanotte' },
		ja: { morning: 'Ohayou gozaimasu', afternoon: 'Konnichiwa', evening: 'Konbanwa', night: 'Oyasuminasai' },
		zh: { morning: 'Zao shang hao', afternoon: 'Xia wu hao', evening: 'Wan shang hao', night: 'Wan an' },
		ko: { morning: 'Joh-eun achim', afternoon: 'Annyeonghaseyo', evening: 'Annyeonghaseyo', night: 'Annyeonghi jumuseyo' },
	};

	/** Resolve language code from the agentLanguage setting (e.g. "english" -> "en", "es" -> "es"). */
	function resolveLanguageCode(lang: string | null): string {
		if (!lang) return 'en';
		const lower = lang.toLowerCase().trim();
		// Direct code match
		if (greetings[lower]) return lower;
		// Full language name map
		const nameMap: Record<string, string> = {
			english: 'en', spanish: 'es', french: 'fr', portuguese: 'pt',
			german: 'de', italian: 'it', japanese: 'ja', chinese: 'zh', korean: 'ko',
		};
		return nameMap[lower] ?? 'en';
	}

	function getTimePeriod(): TimePeriod {
		const hour = new Date().getHours();
		if (hour >= 5 && hour < 12) return 'morning';
		if (hour >= 12 && hour < 17) return 'afternoon';
		if (hour >= 17 && hour < 21) return 'evening';
		return 'night';
	}

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
		isAdmin?: boolean;
	}

	interface DashboardStats {
		system_count?: number;
		knowledge_doc_count?: number;
		conversation_count?: number;
		message_count?: number;
		active_user_count?: number;
	}

	let systemCount = $state(0);
	let docCount = $state(0);
	let conversationCount = $state(0);
	let activeUserCount = $state(0);
	let mounted = $state(false);
	let apiSuggestions = $state<Suggestion[]>([]);

	$effect(() => {
		(async () => {
			const [statsResult, suggestionsResult] = await Promise.allSettled([
				apiJson<DashboardStats>('/admin/dashboard/stats'),
				apiJson<{ suggestions: APISuggestion[] }>('/chat/suggestions'),
			]);

			if (statsResult.status === 'fulfilled') {
				systemCount = statsResult.value.system_count ?? 0;
				docCount = statsResult.value.knowledge_doc_count ?? 0;
				conversationCount = statsResult.value.conversation_count ?? 0;
				activeUserCount = statsResult.value.active_user_count ?? 0;
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
			}, 60);
		})();
	});

	// -----------------------------------------------------------------------
	// Derived state
	// -----------------------------------------------------------------------

	let firstName = $derived($currentUser?.displayName?.split(' ')[0] ?? null);
	let timePeriod = $derived(getTimePeriod());
	let langCode = $derived(resolveLanguageCode($userSettings.agentLanguage));
	let localizedGreetings = $derived(greetings[langCode] ?? greetings.en);

	let greeting = $derived(
		firstName
			? `${localizedGreetings[timePeriod]}, ${firstName}`
			: localizedGreetings[timePeriod]
	);

	let userContext = $derived.by(() => {
		const parts: string[] = [];
		if ($currentUser?.department) parts.push($currentUser.department);
		if ($isAdmin) parts.push('Admin');
		else if ($currentUser?.roles?.length) {
			const role = $currentUser.roles[0];
			if (role && role !== 'user') {
				parts.push(role.charAt(0).toUpperCase() + role.slice(1));
			}
		}
		return parts.join(' \u00b7 ');
	});

	let hasStats = $derived(systemCount > 0 || docCount > 0 || conversationCount > 0);

	let statItems = $derived.by(() => {
		const items: { label: string; value: number; icon: LucideIcon }[] = [];
		if (docCount > 0) items.push({ label: docCount === 1 ? 'doc' : 'docs', value: docCount, icon: FileText });
		if (systemCount > 0) items.push({ label: systemCount === 1 ? 'system' : 'systems', value: systemCount, icon: Server });
		if (conversationCount > 0) items.push({ label: conversationCount === 1 ? 'conversation' : 'conversations', value: conversationCount, icon: MessageSquare });
		if (activeUserCount > 0) items.push({ label: activeUserCount === 1 ? 'active user' : 'active users', value: activeUserCount, icon: Layers });
		return items;
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

	// (cards use a single consistent accent treatment for professionalism)
</script>

<div class="relative flex min-h-full flex-col items-center justify-center px-4 py-8">
	<!-- Hero section -->
	<div
		class="mb-8 flex flex-col items-center gap-5 transition-all duration-700 ease-out
			{mounted ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-3'}"
	>
		<!-- Avatar -->
		<div class="flex h-14 w-14 items-center justify-center rounded-full bg-surface-elevated shadow-sm ring-1 ring-border/30">
			<EmberAvatar size={34} />
		</div>

		<!-- Greeting text -->
		<div class="text-center">
			<h2 class="text-3xl font-bold tracking-tight text-text-primary">
				{greeting}
			</h2>
			{#if userContext}
				<p
					class="mt-1.5 text-xs font-medium uppercase tracking-widest text-text-secondary/70"
				>
					{userContext}
				</p>
			{/if}
			<p class="mx-auto mt-3 max-w-md text-sm leading-relaxed text-text-secondary">
				I'm Ember, your AI assistant. How can I help you today?
			</p>
		</div>
	</div>

	<!-- Stats bar -->
	{#if hasStats}
		<div
			class="mb-8 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 transition-all duration-700 delay-150 ease-out
				{mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}"
		>
			{#each statItems as stat, i}
				{#if i > 0}
					<span class="hidden h-3 w-px bg-border sm:block"></span>
				{/if}
				<span class="flex items-center gap-1.5 text-xs text-text-secondary">
					<stat.icon size={12} class="opacity-50" />
					<span class="font-semibold tabular-nums text-text-primary">{stat.value}</span>
					{stat.label}
				</span>
			{/each}
		</div>
	{/if}

	<!-- Suggestion cards -->
	<div class="grid w-full max-w-2xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each suggestions as suggestion, i}
			<button
				type="button"
				class="group flex items-start gap-3 rounded-xl border border-border/50
					bg-surface px-4 py-3.5 text-left transition-all duration-200
					hover:border-border hover:bg-surface-elevated hover:shadow-sm
					{mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}"
				style="transition-delay: {mounted ? 200 + i * 60 : 0}ms"
				onclick={() => onSuggestionClick(suggestion.text)}
			>
				<span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-secondary text-text-secondary transition-colors duration-150 group-hover:bg-accent/10 group-hover:text-accent">
					<suggestion.icon size={16} />
				</span>
				<div class="min-w-0 pt-0.5">
					<div class="text-[13px] font-medium text-text-primary">
						{suggestion.title}
					</div>
					<div class="mt-0.5 text-[12px] leading-relaxed text-text-secondary/70">
						{suggestion.description}
					</div>
				</div>
			</button>
		{/each}
	</div>
</div>

<style>
</style>
