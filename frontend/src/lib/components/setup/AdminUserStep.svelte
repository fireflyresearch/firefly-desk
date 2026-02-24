<!--
  AdminUserStep.svelte -- Admin user creation step of the setup wizard.

  Collects username, email, display name, and password for the initial
  administrator account.  Validates input client-side and POSTs to the
  /setup/create-admin endpoint.  OIDC/SSO configuration is deferred to
  the Admin > SSO panel after first login.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight, Loader2, XCircle } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface AdminUserStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: AdminUserStepProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let username = $state('');
	let email = $state('');
	let displayName = $state('');
	let password = $state('');
	let confirmPassword = $state('');

	let submitting = $state(false);
	let errorMessage = $state('');

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

	let usernameError = $derived(
		username.length > 0 && username.trim().length === 0
			? 'Username is required.'
			: ''
	);

	let emailError = $derived(
		email.length > 0 && !emailRegex.test(email)
			? 'Please enter a valid email address.'
			: ''
	);

	let passwordError = $derived(
		password.length > 0 && password.length < 8
			? 'Password must be at least 8 characters.'
			: ''
	);

	let confirmError = $derived(
		confirmPassword.length > 0 && confirmPassword !== password
			? 'Passwords do not match.'
			: ''
	);

	let isValid = $derived(
		username.trim().length > 0 &&
			emailRegex.test(email) &&
			password.length >= 8 &&
			confirmPassword === password
	);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleSubmit() {
		if (!isValid || submitting) return;

		submitting = true;
		errorMessage = '';

		try {
			const result = await apiJson<{ success: boolean; user_id: string }>(
				'/setup/create-admin',
				{
					method: 'POST',
					body: JSON.stringify({
						username: username.trim(),
						email: email.trim(),
						display_name: displayName.trim() || username.trim(),
						password
					})
				}
			);

			onNext({
				admin_user: {
					username: username.trim(),
					user_id: result.user_id
				}
			});
		} catch (e) {
			errorMessage =
				e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Admin Account</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Create the first administrator account. You will use these credentials to
		log in after setup.
	</p>

	<div class="mt-6 space-y-5">
		<!-- Error banner -->
		{#if errorMessage}
			<div
				class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
			>
				<XCircle size={18} class="mt-0.5 shrink-0" />
				<span>{errorMessage}</span>
			</div>
		{/if}

		<!-- Username -->
		<div>
			<label for="admin-username" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Username
			</label>
			<input
				id="admin-username"
				type="text"
				bind:value={username}
				placeholder="admin"
				autocomplete="username"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
			{#if usernameError}
				<p class="mt-1 text-xs text-danger">{usernameError}</p>
			{/if}
		</div>

		<!-- Email -->
		<div>
			<label for="admin-email" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Email
			</label>
			<input
				id="admin-email"
				type="email"
				bind:value={email}
				placeholder="admin@example.com"
				autocomplete="email"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
			{#if emailError}
				<p class="mt-1 text-xs text-danger">{emailError}</p>
			{/if}
		</div>

		<!-- Display Name -->
		<div>
			<label for="admin-display-name" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Display Name <span class="text-text-secondary/60">(optional)</span>
			</label>
			<input
				id="admin-display-name"
				type="text"
				bind:value={displayName}
				placeholder="Admin"
				autocomplete="name"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
		</div>

		<!-- Password -->
		<div>
			<label for="admin-password" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Password
			</label>
			<input
				id="admin-password"
				type="password"
				bind:value={password}
				placeholder="At least 8 characters"
				autocomplete="new-password"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
			{#if passwordError}
				<p class="mt-1 text-xs text-danger">{passwordError}</p>
			{/if}
		</div>

		<!-- Confirm Password -->
		<div>
			<label for="admin-confirm-password" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Confirm Password
			</label>
			<input
				id="admin-confirm-password"
				type="password"
				bind:value={confirmPassword}
				placeholder="Re-enter your password"
				autocomplete="new-password"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
			{#if confirmError}
				<p class="mt-1 text-xs text-danger">{confirmError}</p>
			{/if}
		</div>

		<!-- SSO note -->
		<p class="rounded-lg bg-surface-secondary px-4 py-3 text-xs text-text-secondary">
			OIDC/SSO can be configured later in
			<strong class="font-medium text-text-primary">Admin &gt; SSO</strong>
			after your first login.
		</p>
	</div>

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Navigation -->
	<div class="mt-8 flex items-center justify-between border-t border-border pt-4">
		<button
			type="button"
			onclick={onBack}
			class="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			<ArrowLeft size={16} />
			Back
		</button>
		<button
			type="button"
			onclick={handleSubmit}
			disabled={!isValid || submitting}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
		>
			{#if submitting}
				<Loader2 size={16} class="animate-spin" />
				Creating...
			{:else}
				Continue
				<ArrowRight size={16} />
			{/if}
		</button>
	</div>
</div>
