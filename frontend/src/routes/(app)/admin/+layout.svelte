<!--
  Admin layout - Sidebar navigation with role guard.

  Only visible to users with the "admin" role. Renders a sidebar
  with grouped, collapsible navigation sections alongside the child page.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { fade } from 'svelte/transition';
	import {
		ArrowLeft,
		MessageSquare,
		LayoutDashboard,
		Database,
		Key,
		BookOpen,
		Network,
		FileText,
		Bot,
		Users,
		Download,
		Shield,
		ShieldAlert,
		FileCode,
		Wrench,
		GitBranch,
		GitFork,
		FolderOpen,
		HelpCircle,
		Cloud,
		Globe,
		ChevronRight,
		ChevronDown,
		Cpu,
		Lock,
		Settings,
		Mail,
		Activity,
		Webhook,
		Radio,
		ArrowUpRight
	} from 'lucide-svelte';
	import { isAdmin } from '$lib/stores/user.js';

	let { children } = $props();

	// Top-level item (always visible, not in a group)
	const dashboardItem = { href: '/admin', label: 'Dashboard', icon: LayoutDashboard, exact: true };

	// Grouped navigation
	const navGroups = [
		{
			key: 'content',
			label: 'Content & Data',
			icon: Database,
			items: [
				{ href: '/admin/workspaces', label: 'Workspaces', icon: FolderOpen },
				{ href: '/admin/catalog', label: 'System Catalog', icon: Network },
				{ href: '/admin/knowledge', label: 'Knowledge Base', icon: BookOpen },
				{ href: '/admin/processes', label: 'Processes', icon: GitBranch },
			],
		},
		{
			key: 'ai',
			label: 'AI Configuration',
			icon: Cpu,
			items: [
				{ href: '/admin/agent', label: 'Agent', icon: Bot },
				{ href: '/admin/email', label: 'Email', icon: Mail },
				{ href: '/admin/llm-providers', label: 'LLM Providers', icon: Cpu },
				{ href: '/admin/prompts', label: 'Prompts', icon: FileCode },
				{ href: '/admin/tools', label: 'Tools', icon: Wrench },
			],
		},
		{
			key: 'security',
			label: 'Security & Access',
			icon: Lock,
			items: [
				{ href: '/admin/users', label: 'Users & Roles', icon: Users },
				{ href: '/admin/credentials', label: 'Credentials', icon: Key },
				{ href: '/admin/sso', label: 'Single Sign-On', icon: Shield },
			],
		},
		{
			key: 'operations',
			label: 'Operations',
			icon: Settings,
			items: [
				{ href: '/admin/jobs', label: 'Jobs', icon: Activity },
				{ href: '/admin/webhooks', label: 'Webhooks', icon: Webhook },
				{ href: '/admin/callbacks', label: 'Callbacks', icon: ArrowUpRight },
				{ href: '/admin/dev-tools', label: 'Dev Tools', icon: Radio },
				{ href: '/admin/audit', label: 'Audit Log', icon: FileText },
				{ href: '/admin/exports', label: 'Exports', icon: Download },
				{ href: '/admin/git-providers', label: 'Git Providers', icon: GitFork },
				{ href: '/admin/document-sources', label: 'Document Sources', icon: Cloud },
				{ href: '/admin/search-engine', label: 'Search Engine', icon: Globe },
			],
		},
	];

	// Bottom item (pinned outside groups)
	const helpItem = { href: '/admin/help', label: 'Help & Guides', icon: HelpCircle };

	// Collapse state — all expanded by default
	let collapsedSections = $state<Set<string>>(new Set());

	function toggleSection(key: string) {
		const next = new Set(collapsedSections);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		collapsedSections = next;
	}

	function isActive(href: string, exact: boolean = false): boolean {
		return exact ? currentPath === href : currentPath.startsWith(href);
	}

	let currentPath = $derived($page.url.pathname);
	let dashActive = $derived(isActive(dashboardItem.href, true));
	let helpActive = $derived(isActive(helpItem.href));
</script>

{#if $isAdmin}
	<div class="flex h-full">
		<!-- Sidebar -->
		<nav class="flex w-56 shrink-0 flex-col overflow-y-auto border-r border-border/50 bg-surface-secondary">
			<div class="flex flex-1 flex-col p-2 pt-2">
				<!-- Back to Chat -->
				<a
					href="/"
					class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-text-secondary transition-all hover:bg-ember/5 hover:text-ember"
				>
					<ArrowLeft size={16} />
					<MessageSquare size={14} />
					Back to Chat
				</a>
				<div class="mx-2 my-2 h-px bg-border/15"></div>

				<!-- Dashboard (always visible) -->
				<a
					href={dashboardItem.href}
					class="group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-all duration-150
						{dashActive
						? 'bg-surface-elevated font-semibold text-text-primary shadow-[0_1px_3px_rgba(0,0,0,0.06)]'
						: 'text-text-secondary hover:bg-surface-hover/50 hover:text-text-primary'}"
				>
					{#if dashActive}
						<div class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent shadow-[0_0_6px_var(--color-glow-accent)]"></div>
					{/if}
					<dashboardItem.icon size={16} class={dashActive ? 'text-accent' : ''} />
					{dashboardItem.label}
				</a>

				<div class="mx-2 my-2 h-px bg-border/15"></div>

				<!-- Grouped sections -->
				{#each navGroups as group}
					{@const collapsed = collapsedSections.has(group.key)}
					<div class="mb-0.5">
						<button
							type="button"
							onclick={() => toggleSection(group.key)}
							class="group/section flex w-full items-center gap-1.5 px-3 pb-1 pt-2.5 transition-colors"
						>
							<span class="flex h-4 w-4 items-center justify-center text-text-secondary/40 transition-colors group-hover/section:text-text-secondary/60">
								{#if collapsed}
									<ChevronRight size={11} />
								{:else}
									<ChevronDown size={11} />
								{/if}
							</span>
							<group.icon size={10} class="text-text-secondary/35" />
							<span class="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-text-secondary/40">
								{group.label}
							</span>
							<span class="ml-auto rounded-full bg-surface-hover/60 px-1.5 py-px text-[9px] font-medium tabular-nums text-text-secondary/50">
								{group.items.length}
							</span>
						</button>
						{#if !collapsed}
							<div class="space-y-px pb-1">
								{#each group.items as item}
									{@const active = isActive(item.href)}
									<a
										href={item.href}
										class="group relative flex items-center gap-2.5 rounded-lg mx-1 px-2.5 py-[7px] text-[13px] transition-all duration-150
											{active
											? 'bg-surface-elevated font-semibold text-text-primary shadow-[0_1px_3px_rgba(0,0,0,0.06)]'
											: 'text-text-secondary hover:bg-surface-hover/50 hover:text-text-primary'}"
									>
										{#if active}
											<div class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent shadow-[0_0_6px_var(--color-glow-accent)]"></div>
										{/if}
										<item.icon size={15} class={active ? 'text-accent' : 'text-text-secondary/50'} />
										{item.label}
									</a>
								{/each}
							</div>
						{/if}
					</div>
					<div class="mx-3 my-1 h-px bg-border/10"></div>
				{/each}

				<!-- Spacer to push Help to bottom -->
				<div class="flex-1"></div>

				<!-- Help (pinned at bottom) -->
				<div class="mx-2 mb-1 mt-2 h-px bg-border/15"></div>
				<a
					href={helpItem.href}
					class="group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-all duration-150
						{helpActive
						? 'bg-surface-elevated font-semibold text-text-primary shadow-[0_1px_3px_rgba(0,0,0,0.06)]'
						: 'text-text-secondary/60 hover:bg-surface-hover/50 hover:text-text-primary'}"
				>
					{#if helpActive}
						<div class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent shadow-[0_0_6px_var(--color-glow-accent)]"></div>
					{/if}
					<helpItem.icon size={15} class={helpActive ? 'text-accent' : ''} />
					{helpItem.label}
				</a>
			</div>
		</nav>

		<!-- Content area -->
		<div class="min-h-0 flex-1 overflow-hidden">
			{#key currentPath}
				<div class="h-full" in:fade={{ duration: 150, delay: 50 }} out:fade={{ duration: 100 }}>
					{@render children()}
				</div>
			{/key}
		</div>
	</div>
{:else}
	<!-- Access denied -->
	<div class="flex h-full flex-col items-center justify-center gap-3">
		<span class="text-text-secondary/40">
			<ShieldAlert size={48} strokeWidth={1} />
		</span>
		<h2 class="text-lg font-semibold text-text-primary">Access Denied</h2>
		<p class="text-sm text-text-secondary">
			You do not have permission to access the admin console.
		</p>
	</div>
{/if}
