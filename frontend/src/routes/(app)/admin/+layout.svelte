<!--
  Admin layout - Sidebar navigation with role guard.

  Only visible to users with the "admin" role. Renders a sidebar
  with navigation links to each admin section alongside the child page.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import {
		LayoutDashboard,
		Database,
		Key,
		BookOpen,
		FileText,
		Bot,
		Users,
		ShieldAlert
	} from 'lucide-svelte';
	import { isAdmin } from '$lib/stores/user.js';

	let { children } = $props();

	const navItems = [
		{ href: '/admin', label: 'Dashboard', icon: LayoutDashboard, exact: true },
		{ href: '/admin/catalog', label: 'Catalog', icon: Database },
		{ href: '/admin/credentials', label: 'Credentials', icon: Key },
		{ href: '/admin/knowledge', label: 'Knowledge Base', icon: BookOpen },
		{ href: '/admin/audit', label: 'Audit Log', icon: FileText },
		{ href: '/admin/llm-providers', label: 'LLM Providers', icon: Bot },
		{ href: '/admin/users', label: 'Users', icon: Users }
	];

	let currentPath = $derived($page.url.pathname);
</script>

{#if $isAdmin}
	<div class="flex h-full">
		<!-- Sidebar -->
		<nav class="flex w-56 shrink-0 flex-col border-r border-border bg-surface-secondary">
			<div class="border-b border-border px-4 py-3">
				<h2 class="text-sm font-semibold text-text-primary">Administration</h2>
			</div>

			<ul class="flex flex-col gap-0.5 p-2">
				{#each navItems as item}
					{@const active = item.exact
						? currentPath === item.href
						: currentPath.startsWith(item.href)}
					<li>
						<a
							href={item.href}
							class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors
								{active
								? 'bg-accent/10 font-medium text-accent'
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
