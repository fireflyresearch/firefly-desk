<!--
  OIDC callback page.

  Receives the authorization code and state from the URL query params,
  posts them to the backend /api/auth/callback endpoint, and redirects
  to the app root on success.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { Loader2, AlertCircle } from 'lucide-svelte';
	import { apiFetch } from '$lib/services/api.js';

	let error = $state('');
	let processing = $state(true);

	$effect(() => {
		handleCallback();
	});

	async function handleCallback(): Promise<void> {
		const code = $page.url.searchParams.get('code');
		const state = $page.url.searchParams.get('state');
		const errorParam = $page.url.searchParams.get('error');
		const errorDescription = $page.url.searchParams.get('error_description');

		// Handle error responses from the IdP
		if (errorParam) {
			error = errorDescription || errorParam;
			processing = false;
			return;
		}

		if (!code || !state) {
			error = 'Missing authorization code or state parameter.';
			processing = false;
			return;
		}

		// Validate state against what we stored before redirect
		const savedState = sessionStorage.getItem('oidc_state');
		if (savedState && savedState !== state) {
			error = 'State mismatch. This may indicate a CSRF attack. Please try again.';
			processing = false;
			return;
		}
		sessionStorage.removeItem('oidc_state');

		try {
			await apiFetch('/auth/callback', {
				method: 'POST',
				body: JSON.stringify({ code, state })
			});
			// The backend sets the session cookie; redirect to app root
			await goto('/', { replaceState: true });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Authentication failed. Please try again.';
			processing = false;
		}
	}
</script>

<svelte:head>
	<title>Completing Sign In - Firefly Desk</title>
</svelte:head>

<div class="flex min-h-screen items-center justify-center bg-surface-secondary px-4">
	{#if processing}
		<div class="flex flex-col items-center gap-3">
			<Loader2 size={32} class="animate-spin text-accent" />
			<p class="text-sm text-text-secondary">Completing sign-in...</p>
		</div>
	{:else if error}
		<div
			class="w-full max-w-sm rounded-xl border border-border bg-surface px-8 py-10 shadow-sm"
		>
			<div class="flex flex-col items-center gap-4">
				<div class="rounded-full bg-danger/10 p-3">
					<AlertCircle size={24} class="text-danger" />
				</div>
				<h1 class="text-lg font-semibold text-text-primary">
					Authentication Failed
				</h1>
				<p class="text-center text-sm text-text-secondary">
					{error}
				</p>
				<a
					href="/auth/login"
					class="mt-2 inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2
						   text-sm font-medium text-white transition-colors hover:bg-accent-hover"
				>
					Try Again
				</a>
			</div>
		</div>
	{/if}
</div>
