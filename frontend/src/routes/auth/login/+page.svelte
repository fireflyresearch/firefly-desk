<!--
  Login page -- supports local username/password authentication
  and OIDC provider sign-in when providers are configured.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, LogIn, AlertCircle } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import Logo from '$lib/components/layout/Logo.svelte';

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
	// State -- OIDC
	// -----------------------------------------------------------------------

	let providers = $state<ProviderInfo[]>([]);
	let loading = $state(true);
	let error = $state('');
	let redirectingId = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// State -- Local login
	// -----------------------------------------------------------------------

	let localUsername = $state('');
	let localPassword = $state('');
	let localLoading = $state(false);
	let localError = $state('');

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
	// Local login flow
	// -----------------------------------------------------------------------

	async function handleLocalLogin() {
		localLoading = true;
		localError = '';
		try {
			await apiJson('/auth/login', {
				method: 'POST',
				body: JSON.stringify({ username: localUsername, password: localPassword })
			});
			// Cookie set by backend; redirect to app
			window.location.href = '/';
		} catch (e) {
			localError = e instanceof Error ? e.message : 'Login failed';
		} finally {
			localLoading = false;
		}
	}

	// -----------------------------------------------------------------------
	// OIDC login flow
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
			<Logo class="h-8" />
			<h1 class="text-xl font-semibold text-text-primary">Sign in</h1>
			<p class="text-sm text-text-secondary">
				Sign in to your account
			</p>
		</div>

		<!-- Local login error banner -->
		{#if localError}
			<div
				class="mb-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2.5 text-sm text-danger"
			>
				<AlertCircle size={16} class="mt-0.5 shrink-0" />
				<span>{localError}</span>
			</div>
		{/if}

		<!-- Local login form -->
		<form onsubmit={(e) => { e.preventDefault(); handleLocalLogin(); }}>
			<div class="flex flex-col gap-3">
				<div>
					<label for="username" class="mb-1 block text-sm font-medium text-text-primary">
						Username
					</label>
					<input
						id="username"
						type="text"
						autocomplete="username"
						required
						bind:value={localUsername}
						disabled={localLoading}
						placeholder="Enter your username"
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
					/>
				</div>
				<div>
					<label for="password" class="mb-1 block text-sm font-medium text-text-primary">
						Password
					</label>
					<input
						id="password"
						type="password"
						autocomplete="current-password"
						required
						bind:value={localPassword}
						disabled={localLoading}
						placeholder="Enter your password"
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
					/>
				</div>
				<button
					type="submit"
					disabled={localLoading}
					class="mt-1 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg
						   bg-accent px-4 py-2.5 text-sm font-medium text-white
						   transition-colors hover:bg-accent-hover focus-visible:outline-2
						   focus-visible:outline-offset-2 focus-visible:outline-accent
						   disabled:cursor-not-allowed disabled:opacity-50"
				>
					{#if localLoading}
						<Loader2 size={16} class="animate-spin" />
						Signing in...
					{:else}
						<LogIn size={16} />
						Sign In
					{/if}
				</button>
			</div>
		</form>

		<!-- OIDC section (only if providers exist) -->
		{#if loading}
			<div class="flex items-center justify-center py-6">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else if providers.length > 0}
			<!-- Divider -->
			<div class="relative my-6">
				<div class="absolute inset-0 flex items-center">
					<div class="w-full border-t border-border"></div>
				</div>
				<div class="relative flex justify-center text-xs">
					<span class="bg-surface px-3 text-text-secondary">or continue with</span>
				</div>
			</div>

			<!-- OIDC error banner -->
			{#if error}
				<div
					class="mb-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2.5 text-sm text-danger"
				>
					<AlertCircle size={16} class="mt-0.5 shrink-0" />
					<span>{error}</span>
				</div>
			{/if}

			<!-- Provider buttons -->
			<div class="flex flex-col gap-3">
				{#each providers as provider}
					<button
						type="button"
						onclick={() => handleLogin(provider)}
						disabled={redirectingId !== null}
						class="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg
							   border border-border bg-surface px-4 py-2.5 text-sm font-medium text-text-primary
							   transition-colors hover:bg-surface-secondary focus-visible:outline-2
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
