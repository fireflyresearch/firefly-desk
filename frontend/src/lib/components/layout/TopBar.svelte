<script lang="ts">
	import {
		PanelLeft,
		PanelLeftClose,
		Sun,
		Moon,
		User,
		Shield,
		LogOut,
		Palette
	} from 'lucide-svelte';
	import Logo from '$lib/components/layout/Logo.svelte';
	import ModelStatus from '$lib/components/chat/ModelStatus.svelte';
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
</script>

<svelte:window onclick={handleWindowClick} />

<header
	class="relative z-40 flex h-14 shrink-0 items-center border-b border-border/50 bg-surface/80 px-4 backdrop-blur-xl"
>
	<!-- Bottom border glow (visible in dark mode) -->
	<div
		class="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-ember/20 to-transparent opacity-0 transition-opacity dark:opacity-100"
	></div>

	<!-- Left: Sidebar toggle + Logo -->
	<div class="flex items-center gap-3">
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
		<Logo class="h-7 text-text-primary" />
	</div>

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Right: actions -->
	<div class="flex items-center gap-1">
		{#if $currentUser?.devMode}
			<span
				class="mr-1 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-0.5 text-xs font-medium text-warning"
			>
				Dev
			</span>
		{/if}

		<!-- Model status indicator -->
		<ModelStatus />

		<button
			type="button"
			onclick={toggleDarkMode}
			class="btn-hover flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
			aria-label={$resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
		>
			{#if $resolvedTheme === 'dark'}
				<Sun size={16} />
			{:else}
				<Moon size={16} />
			{/if}
		</button>

		<!-- User avatar with dropdown -->
		<div class="relative ml-1" data-user-dropdown>
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
					class="absolute right-0 top-full z-50 mt-1 w-52 rounded-lg border border-border bg-surface-elevated/95 shadow-xl backdrop-blur-xl"
					role="menu"
				>
					<div class="border-b border-border px-3 py-2">
						<p class="text-sm font-medium text-text-primary">{displayName}</p>
						{#if $currentUser?.email}
							<p class="mt-0.5 truncate text-xs text-text-secondary">{$currentUser.email}</p>
						{/if}
						{#if $currentUser?.roles.length}
							<div class="mt-1.5 flex flex-wrap gap-1">
								{#each $currentUser.roles as role}
									<span
										class="rounded-full border border-ember/30 bg-ember/10 px-1.5 py-0.5 text-[10px] font-medium text-ember"
									>
										{role}
									</span>
								{/each}
							</div>
						{/if}
					</div>
					<ul class="py-1">
						<li>
							<a
								href="/settings"
								onclick={closeDropdown}
								class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary no-underline transition-colors hover:bg-surface-hover hover:text-text-primary"
								role="menuitem"
							>
								<User size={14} />
								Profile
							</a>
						</li>
						<li>
							<a
								href="/settings/appearance"
								onclick={closeDropdown}
								class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary no-underline transition-colors hover:bg-surface-hover hover:text-text-primary"
								role="menuitem"
							>
								<Palette size={14} />
								Appearance
							</a>
						</li>
						{#if $isAdmin}
							<li>
								<a
									href="/admin"
									onclick={closeDropdown}
									class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary no-underline transition-colors hover:bg-surface-hover hover:text-text-primary"
									role="menuitem"
								>
									<Shield size={14} />
									Admin Console
								</a>
							</li>
						{/if}
						<li class="border-t border-border">
							<a
								href="/auth/login"
								onclick={closeDropdown}
								class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary no-underline transition-colors hover:bg-surface-hover hover:text-text-primary"
								role="menuitem"
							>
								<LogOut size={14} />
								Sign Out
							</a>
						</li>
					</ul>
				</div>
			{/if}
		</div>
	</div>
</header>
