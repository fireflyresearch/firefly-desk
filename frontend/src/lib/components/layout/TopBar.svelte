<script lang="ts">
	import { Settings, Sun, Moon } from 'lucide-svelte';
	import logo from '$lib/assets/logo.svg';

	interface TopBarProps {
		title?: string;
		userName?: string;
	}

	let { title = 'Firefly Desk', userName = 'User' }: TopBarProps = $props();

	let darkMode = $state(false);

	let initials = $derived(
		userName
			.split(' ')
			.map((part) => part[0])
			.join('')
			.toUpperCase()
			.slice(0, 2)
	);

	function toggleDarkMode() {
		darkMode = !darkMode;
	}
</script>

<header
	class="flex h-14 shrink-0 items-center border-b border-border bg-surface px-4"
>
	<!-- Left: Logo -->
	<div class="flex items-center gap-2">
		<img src={logo} alt={title} class="h-6" />
	</div>

	<!-- Center: empty for now (search will go here) -->
	<div class="flex-1"></div>

	<!-- Right: actions -->
	<div class="flex items-center gap-2">
		<button
			type="button"
			onclick={toggleDarkMode}
			class="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
		>
			{#if darkMode}
				<Sun size={18} />
			{:else}
				<Moon size={18} />
			{/if}
		</button>

		<button
			type="button"
			class="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			aria-label="Settings"
		>
			<Settings size={18} />
		</button>

		<div
			class="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-xs font-medium text-white select-none"
			title={userName}
		>
			{initials}
		</div>
	</div>
</header>
