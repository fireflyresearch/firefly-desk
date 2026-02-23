<!--
  Settings layout - Sidebar navigation for settings sub-pages.

  Renders a sidebar with navigation links to each settings section
  alongside the child page. Pattern mirrors the admin layout.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { ArrowLeft, MessageSquare, User, Palette, Info } from 'lucide-svelte';

	let { children } = $props();

	const navItems = [
		{ href: '/settings', label: 'Profile', icon: User, exact: true },
		{ href: '/settings/appearance', label: 'Appearance', icon: Palette },
		{ href: '/settings/about', label: 'About', icon: Info }
	];

	let currentPath = $derived($page.url.pathname);

	let currentPageLabel = $derived(
		navItems.find((item) =>
			item.exact
				? currentPath === item.href
				: currentPath.startsWith(item.href) && item.href !== '/settings'
		)?.label ?? ''
	);
</script>

<div class="flex h-full">
	<!-- Sidebar -->
	<nav class="flex w-56 shrink-0 flex-col border-r border-border/50 bg-surface-secondary">
		<div class="border-b border-border/50 px-4 py-3">
			<nav class="flex items-center gap-1.5 text-xs text-text-secondary" aria-label="Breadcrumb">
				<a href="/" class="transition-colors hover:text-text-primary">Chat</a>
				<span class="text-text-secondary/40">&rsaquo;</span>
				<span class="font-medium text-text-primary">Settings</span>
				{#if currentPageLabel}
					<span class="text-text-secondary/40">&rsaquo;</span>
					<span class="text-text-secondary">{currentPageLabel}</span>
				{/if}
			</nav>
			<h2 class="mt-1 text-sm font-semibold text-text-primary">Settings</h2>
		</div>

		<ul class="flex flex-col gap-0.5 p-2">
			<!-- Back to Chat -->
			<li>
				<a
					href="/"
					class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary transition-all hover:bg-ember/5 hover:text-ember"
				>
					<ArrowLeft size={16} />
					<MessageSquare size={14} />
					Back to Chat
				</a>
			</li>
			<li><div class="my-1 border-b border-border/50"></div></li>
			{#each navItems as item}
				{@const active = item.exact
					? currentPath === item.href
					: currentPath.startsWith(item.href)}
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
