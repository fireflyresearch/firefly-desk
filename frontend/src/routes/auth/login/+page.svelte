<!--
  Login page -- redirects the user to the configured OIDC provider.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { buildAuthUrl } from '$lib/services/auth';
	import logo from '$lib/assets/logo.svg';

	let { data } = $props();

	function handleLogin(): void {
		const state = crypto.randomUUID();
		sessionStorage.setItem('oidc_state', state);

		const url = buildAuthUrl(data.issuerUrl, data.clientId, data.redirectUri, state);
		window.location.href = url;
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
			<h1 class="text-xl font-semibold text-text-primary">
				Sign in
			</h1>
			<p class="text-sm text-text-secondary">
				Authenticate with your organization account
			</p>
		</div>

		<!-- SSO button -->
		<button
			type="button"
			onclick={handleLogin}
			class="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg
				   bg-accent px-4 py-2.5 text-sm font-medium text-white
				   transition-colors hover:bg-accent-hover focus-visible:outline-2
				   focus-visible:outline-offset-2 focus-visible:outline-accent"
		>
			Sign in with SSO
		</button>
	</div>
</div>
