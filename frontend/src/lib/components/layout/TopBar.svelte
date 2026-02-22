<script lang="ts">
	import {
		PanelLeft,
		PanelLeftClose,
		Settings,
		Sun,
		Moon,
		User,
		Shield,
		LogOut,
		MessageSquare
	} from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Logo from '$lib/components/layout/Logo.svelte';
	import { resolvedTheme, setTheme } from '$lib/stores/theme';
	import { currentUser, isAdmin } from '$lib/stores/user.js';

	interface TopBarProps {
		title?: string;
		userName?: string;
		onToggleSidebar?: () => void;
		sidebarOpen?: boolean;
	}

	let {
		title = 'Firefly Desk',
		userName = 'User',
		onToggleSidebar,
		sidebarOpen = true
	}: TopBarProps = $props();

	let dropdownOpen = $state(false);

	/** Resolved display name -- prefer currentUser store, fall back to prop. */
	let displayName = $derived($currentUser?.displayName ?? userName);

	let initials = $derived(
		displayName
			.split(' ')
			.map((part) => part[0])
			.join('')
			.toUpperCase()
			.slice(0, 2)
	);

	/** Determine active navigation tab from the current URL path. */
	let activeTab = $derived.by(() => {
		const path = $page.url.pathname;
		if (path.startsWith('/admin')) return 'admin';
		return 'chat';
	});

	function toggleDarkMode() {
		setTheme($resolvedTheme === 'dark' ? 'light' : 'dark');
	}

	function toggleDropdown() {
		dropdownOpen = !dropdownOpen;
	}

	function closeDropdown() {
		dropdownOpen = false;
	}

	function handleWindowClick(event: MouseEvent) {
		const target = event.target as HTMLElement;
		if (!target.closest('[data-user-dropdown]')) {
			dropdownOpen = false;
		}
	}

	function navigateToTab(tab: 'chat' | 'admin') {
		if (tab === 'chat') goto('/');
		else if (tab === 'admin') goto('/admin');
	}
</script>

<svelte:window onclick={handleWindowClick} />

<header
	class="relative flex h-14 shrink-0 items-center border-b border-border/50 bg-surface/80 px-4 backdrop-blur-xl"
>
	<!-- Bottom border glow (visible in dark mode) -->
	<div
		class="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-ember/20 to-transparent opacity-0 transition-opacity dark:opacity-100"
	></div>

	<!-- Left: Sidebar toggle + Logo -->
	<div class="flex items-center gap-2">
		{#if onToggleSidebar}
			<button
				type="button"
				onclick={onToggleSidebar}
				class="btn-hover flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
				aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
			>
				{#if sidebarOpen}
					<PanelLeftClose size={18} class="transition-transform duration-200" />
				{:else}
					<PanelLeft size={18} class="transition-transform duration-200" />
				{/if}
			</button>
		{/if}
		<Logo class="h-6 text-text-primary" />
	</div>

	<!-- Center: Navigation tabs -->
	<nav class="flex flex-1 items-center justify-center gap-1" aria-label="Main navigation">
		<button
			type="button"
			onclick={() => navigateToTab('chat')}
			class="relative flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors
				{activeTab === 'chat'
				? 'text-text-primary'
				: 'text-text-secondary hover:text-text-primary'}"
			aria-current={activeTab === 'chat' ? 'page' : undefined}
		>
			<MessageSquare size={16} />
			Chat
			{#if activeTab === 'chat'}
				<span
					class="absolute bottom-0 left-1/2 h-0.5 w-6 -translate-x-1/2 rounded-full bg-ember"
				></span>
			{/if}
		</button>

		{#if $isAdmin}
			<button
				type="button"
				onclick={() => navigateToTab('admin')}
				class="relative flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors
					{activeTab === 'admin'
					? 'text-text-primary'
					: 'text-text-secondary hover:text-text-primary'}"
				aria-current={activeTab === 'admin' ? 'page' : undefined}
			>
				<Shield size={16} />
				Admin
				{#if activeTab === 'admin'}
					<span
						class="absolute bottom-0 left-1/2 h-0.5 w-6 -translate-x-1/2 rounded-full bg-ember"
					></span>
				{/if}
			</button>
		{/if}
	</nav>

	<!-- Right: actions -->
	<div class="flex items-center gap-2">
		{#if $currentUser?.devMode}
			<span
				class="rounded-full border border-warning/30 bg-warning/10 px-2.5 py-0.5 text-xs font-medium text-warning"
			>
				Dev Mode
			</span>
		{/if}
		<button
			type="button"
			onclick={toggleDarkMode}
			class="btn-hover flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
			aria-label={$resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
		>
			{#if $resolvedTheme === 'dark'}
				<Sun size={18} />
			{:else}
				<Moon size={18} />
			{/if}
		</button>

		<button
			type="button"
			onclick={() => goto('/settings')}
			class="btn-hover flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
			aria-label="Settings"
		>
			<Settings size={18} />
		</button>

		<!-- User avatar with dropdown -->
		<div class="relative" data-user-dropdown>
			<button
				type="button"
				onclick={toggleDropdown}
				class="flex h-8 w-8 items-center justify-center rounded-full select-none cursor-pointer transition-opacity hover:opacity-90 overflow-hidden {$currentUser?.pictureUrl
					? ''
					: 'bg-accent text-xs font-medium text-white'}"
				title={displayName}
				aria-label="User menu"
				aria-expanded={dropdownOpen}
			>
				{#if $currentUser?.pictureUrl}
					<img
						src={$currentUser.pictureUrl}
						alt={displayName}
						class="h-8 w-8 rounded-full object-cover"
					/>
				{:else}
					{initials}
				{/if}
			</button>

			{#if dropdownOpen}
				<div
					class="absolute right-0 top-full z-50 mt-1 w-48 rounded-lg border border-border bg-surface-elevated/95 shadow-xl backdrop-blur-xl"
					role="menu"
				>
					<div class="border-b border-border px-3 py-2">
						<p class="text-sm font-medium text-text-primary">{displayName}</p>
					</div>
					<ul class="py-1">
						<li>
							<button
								type="button"
								onclick={() => {
									closeDropdown();
									goto('/settings');
								}}
								class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
								role="menuitem"
							>
								<User size={14} />
								Profile
							</button>
						</li>
						{#if $isAdmin}
							<li>
								<button
									type="button"
									onclick={() => {
										closeDropdown();
										goto('/admin');
									}}
									class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
									role="menuitem"
								>
									<Shield size={14} />
									Admin Console
								</button>
							</li>
						{/if}
						<li class="border-t border-border">
							<button
								type="button"
								onclick={() => {
									closeDropdown();
									goto('/auth/login');
								}}
								class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
								role="menuitem"
							>
								<LogOut size={14} />
								Sign Out
							</button>
						</li>
					</ul>
				</div>
			{/if}
		</div>
	</div>
</header>
