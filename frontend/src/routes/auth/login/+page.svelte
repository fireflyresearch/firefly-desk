<!--
  Login page -- fetches configured OIDC providers from the backend
  and presents a button for each active provider.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, LogIn, AlertCircle } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import logo from '$lib/assets/logo.svg';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface ProviderInfo {
		id: string;
		provider_type: string;
		display_name: string;
		issuer_url: string;
	}

	interface LoginUrlResponse {
		login_url: string;
		state: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providers = $state<ProviderInfo[]>([]);
	let loading = $state(true);
	let error = $state('');
	let redirectingId = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Load providers on mount
	// -----------------------------------------------------------------------

	$effect(() => {
		loadProviders();
	});

	async function loadProviders() {
		loading = true;
		error = '';
		try {
			providers = await apiJson<ProviderInfo[]>('/auth/providers');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load identity providers';
		} finally {
			loading = false;
		}
	}

	// -----------------------------------------------------------------------
	// Login flow
	// -----------------------------------------------------------------------

	async function handleLogin(provider: ProviderInfo): Promise<void> {
		redirectingId = provider.id;
		error = '';

		try {
			const callbackUri = `${window.location.origin}/auth/callback`;
			const resp = await apiJson<LoginUrlResponse>(
				`/auth/login-url?provider_id=${encodeURIComponent(provider.id)}&redirect_uri=${encodeURIComponent(callbackUri)}`
			);

			// Store state for CSRF validation on callback
			sessionStorage.setItem('oidc_state', resp.state);
			window.location.href = resp.login_url;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to start login';
			redirectingId = null;
		}
	}
</script>

<svelte:head>
	<title>Sign In - Firefly Desk</title>
</svelte:head>

<div class="flex min-h-screen items-center justify-center bg-surface-secondary px-4">
	<div
		class="w-full max-w-sm rounded-xl border border-border bg-surface px-8 py-10 shadow-sm"
	>
		<!-- Branding -->
		<div class="mb-8 flex flex-col items-center gap-4">
			<img src={logo} alt="Firefly Desk" class="h-8" />
			<h1 class="text-xl font-semibold text-text-primary">Sign in</h1>
			<p class="text-sm text-text-secondary">
				Authenticate with your organization account
			</p>
		</div>

		<!-- Error banner -->
		{#if error}
			<div
				class="mb-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2.5 text-sm text-danger"
			>
				<AlertCircle size={16} class="mt-0.5 shrink-0" />
				<span>{error}</span>
			</div>
		{/if}

		<!-- Loading state -->
		{#if loading}
			<div class="flex items-center justify-center py-6">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else if providers.length === 0}
			<div class="py-6 text-center">
				<p class="text-sm text-text-secondary">
					No identity providers configured. Contact your administrator to set up
					single sign-on.
				</p>
			</div>
		{:else}
			<!-- Provider buttons -->
			<div class="flex flex-col gap-3">
				{#each providers as provider}
					<button
						type="button"
						onclick={() => handleLogin(provider)}
						disabled={redirectingId !== null}
						class="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg
							   bg-accent px-4 py-2.5 text-sm font-medium text-white
							   transition-colors hover:bg-accent-hover focus-visible:outline-2
							   focus-visible:outline-offset-2 focus-visible:outline-accent
							   disabled:cursor-not-allowed disabled:opacity-50"
					>
						{#if redirectingId === provider.id}
							<Loader2 size={16} class="animate-spin" />
							Redirecting...
						{:else}
							<LogIn size={16} />
							Sign in with {provider.display_name}
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
