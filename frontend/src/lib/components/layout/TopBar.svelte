<script lang="ts">
	import { Menu, Settings, Sun, Moon, User, Shield, LogOut } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import Logo from '$lib/components/layout/Logo.svelte';
	import { resolvedTheme, setTheme } from '$lib/stores/theme';
	import { currentUser, isAdmin } from '$lib/stores/user.js';

	interface TopBarProps {
		title?: string;
		userName?: string;
		onToggleSidebar?: () => void;
	}

	let { title = 'Firefly Desk', userName = 'User', onToggleSidebar }: TopBarProps = $props();

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
	class="flex h-14 shrink-0 items-center border-b border-border bg-surface px-4"
>
	<!-- Left: Sidebar toggle + Logo -->
	<div class="flex items-center gap-2">
		{#if onToggleSidebar}
			<button
				type="button"
				onclick={onToggleSidebar}
				class="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				aria-label="Toggle sidebar"
			>
				<Menu size={18} />
			</button>
		{/if}
		<Logo class="h-6 text-text-primary" />
	</div>

	<!-- Center: empty for now (search will go here) -->
	<div class="flex-1"></div>

	<!-- Right: actions -->
	<div class="flex items-center gap-2">
		{#if $currentUser?.devMode}
			<span
				class="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400"
			>
				Dev Mode
			</span>
		{/if}
		<button
			type="button"
			onclick={toggleDarkMode}
			class="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
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
			class="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			aria-label="Settings"
		>
			<Settings size={18} />
		</button>

		<!-- User avatar with dropdown -->
		<div class="relative" data-user-dropdown>
			<button
				type="button"
				onclick={toggleDropdown}
				class="flex h-8 w-8 items-center justify-center rounded-full select-none cursor-pointer transition-opacity hover:opacity-90 overflow-hidden {$currentUser?.pictureUrl ? '' : 'bg-accent text-xs font-medium text-white'}"
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
					class="absolute right-0 top-full z-50 mt-1 w-48 rounded-lg border border-border bg-surface shadow-lg"
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
