<!--
  App group layout -- wraps all authenticated routes in the AppShell.

  On mount, checks whether initial setup has been completed. If not,
  redirects to the /setup wizard before rendering any app content.
  If the backend is unreachable, shows a connection error instead of
  proceeding to the app (which would produce 500 errors everywhere).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, WifiOff } from 'lucide-svelte';
	import AppShell from '$lib/components/layout/AppShell.svelte';
	import PanelContainer from '$lib/components/panels/PanelContainer.svelte';
	import SessionTimeoutWarning from '$lib/components/layout/SessionTimeoutWarning.svelte';
	import { panelVisible } from '$lib/stores/panel.js';
	import { initCurrentUser } from '$lib/stores/user.js';
	import { onMount } from 'svelte';

	let { children } = $props();
	let setupChecked = $state(false);
	let backendError = $state(false);

	// -- Session timeout --------------------------------------------------
	const TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
	const WARNING_MS = 5 * 60 * 1000; // Show warning at T-5 min

	let showWarning = $state(false);
	let timeoutId: ReturnType<typeof setTimeout> | null = null;
	let warningId: ReturnType<typeof setTimeout> | null = null;

	function resetTimer() {
		if (timeoutId) clearTimeout(timeoutId);
		if (warningId) clearTimeout(warningId);
		showWarning = false;

		warningId = setTimeout(() => {
			showWarning = true;
		}, TIMEOUT_MS - WARNING_MS);
		timeoutId = setTimeout(() => {
			handleLogout();
		}, TIMEOUT_MS);
	}

	function handleExtend() {
		showWarning = false;
		resetTimer();
	}

	async function handleLogout() {
		try {
			await fetch('/api/auth/logout', { method: 'POST' });
		} catch {
			/* best-effort */
		}
		sessionStorage.clear();
		window.location.href = '/login';
	}

	$effect(() => {
		resetTimer();
		const events = ['click', 'keypress', 'mousemove', 'scroll'];
		const handler = () => resetTimer();
		events.forEach((e) => document.addEventListener(e, handler, { passive: true }));
		return () => {
			events.forEach((e) => document.removeEventListener(e, handler));
			if (timeoutId) clearTimeout(timeoutId);
			if (warningId) clearTimeout(warningId);
		};
	});

	// -- Setup check ------------------------------------------------------
	$effect(() => {
		initCurrentUser();
	});

	async function checkSetup() {
		backendError = false;
		try {
			const res = await fetch('/api/setup/status');
			if (res.ok) {
				const status = await res.json();
				if (!status.setup_completed) {
					window.location.href = '/setup';
					return;
				}
			} else {
				backendError = true;
				return;
			}
		} catch {
			backendError = true;
			return;
		}
		setupChecked = true;
	}

	onMount(() => {
		checkSetup();
	});
</script>

{#if backendError}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<div class="flex flex-col items-center gap-4 text-center">
			<div class="rounded-full bg-danger/10 p-4">
				<WifiOff size={32} class="text-danger" />
			</div>
			<h2 class="text-lg font-semibold text-text-primary">Cannot reach the backend server</h2>
			<p class="max-w-sm text-sm text-text-secondary">
				Make sure the Firefly Desk backend is running on port 8000, then try again.
			</p>
			<button
				type="button"
				onclick={() => checkSetup()}
				class="mt-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90"
			>
				Retry
			</button>
		</div>
	</div>
{:else if setupChecked}
	<AppShell panelVisible={$panelVisible}>
		{#snippet panel()}
			<PanelContainer />
		{/snippet}
		{@render children()}
	</AppShell>
{:else}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<Loader2 size={24} class="animate-spin text-text-secondary" />
	</div>
{/if}

{#if showWarning}
	<SessionTimeoutWarning onExtend={handleExtend} onLogout={handleLogout} />
{/if}
