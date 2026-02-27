<!--
  Settings layout - Sidebar navigation for settings sub-pages.

  Clean sidebar with navigation items and a "Back to Chat" link.
  Matches the admin portal layout pattern.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { ArrowLeft, User, Palette, Info, Brain, Bot } from 'lucide-svelte';

	let { children } = $props();

	const navItems = [
		{ href: '/settings', label: 'Profile', icon: User, exact: true },
		{ href: '/settings/personality', label: 'Agent Personality', icon: Bot },
		{ href: '/settings/memories', label: 'Memories', icon: Brain },
		{ href: '/settings/appearance', label: 'Appearance', icon: Palette },
		{ href: '/settings/about', label: 'About', icon: Info }
	];

	let currentPath = $derived($page.url.pathname);
</script>

<div class="flex h-full">
	<!-- Sidebar -->
	<nav class="flex w-56 shrink-0 flex-col border-r border-border/50 bg-surface-secondary">
		<div class="px-3 pt-4 pb-2">
			<a
				href="/"
				class="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-text-secondary transition-all hover:bg-ember/5 hover:text-ember"
			>
				<ArrowLeft size={16} />
				Back to Chat
			</a>
		</div>

		<div class="px-5 pb-2 pt-1">
			<h2 class="text-xs font-semibold uppercase tracking-wider text-text-secondary">Settings</h2>
		</div>

		<ul class="flex flex-col gap-0.5 px-2 pb-4">
			{#each navItems as item}
				{@const active = item.exact
					? currentPath === item.href
					: currentPath.startsWith(item.href) && item.href !== '/settings'}
				<li>
					<a
						href={item.href}
						class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors
							{active
							? 'bg-ember/10 font-medium text-ember'
							: 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'}"
					>
						<item.icon size={16} />
						{item.label}
					</a>
				</li>
			{/each}

		</ul>
	</nav>

	<!-- Content area -->
	<div class="flex-1 overflow-y-auto">
		{@render children()}
	</div>
</div>
