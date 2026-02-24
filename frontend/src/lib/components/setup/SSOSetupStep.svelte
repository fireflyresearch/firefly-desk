<!--
  SSOSetupStep.svelte -- SSO / OIDC provider configuration step of the setup wizard.

  Allows the user to configure an OIDC identity provider during first-run
  setup. Supports Keycloak, Google, Microsoft, Auth0, Cognito, and Okta.
  Provides "Test Connection" to validate the issuer URL and "Skip" to defer
  SSO configuration to the Admin panel after login.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight, Loader2, XCircle, CheckCircle, Zap } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface TestResult {
		reachable: boolean;
		issuer: string | null;
		error: string | null;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface SSOSetupStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: SSOSetupStepProps = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const PROVIDER_TYPES = [
		{ value: 'keycloak', label: 'Keycloak' },
		{ value: 'google', label: 'Google' },
		{ value: 'microsoft', label: 'Microsoft' },
		{ value: 'auth0', label: 'Auth0' },
		{ value: 'cognito', label: 'AWS Cognito' },
		{ value: 'okta', label: 'Okta' }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providerType = $state('keycloak');
	let displayName = $state('');
	let issuerUrl = $state('');
	let clientId = $state('');
	let clientSecret = $state('');
	let tenantId = $state('');
	let allowedDomains = $state('');

	let submitting = $state(false);
	let testing = $state(false);
	let errorMessage = $state('');
	let testResult = $state<TestResult | null>(null);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let showsTenantId = $derived(providerType === 'microsoft');

	let isValid = $derived(
		displayName.trim().length > 0 &&
			issuerUrl.trim().length > 0 &&
			clientId.trim().length > 0 &&
			clientSecret.trim().length > 0
	);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleTestConnection() {
		if (!issuerUrl.trim() || testing) return;

		testing = true;
		testResult = null;
		errorMessage = '';

		try {
			testResult = await apiJson<TestResult>('/setup/test-sso', {
				method: 'POST',
				body: JSON.stringify({ issuer_url: issuerUrl.trim() })
			});
		} catch (e) {
			testResult = {
				reachable: false,
				issuer: null,
				error: e instanceof Error ? e.message : 'Test failed'
			};
		} finally {
			testing = false;
		}
	}

	async function handleSubmit() {
		if (!isValid || submitting) return;

		submitting = true;
		errorMessage = '';

		const domainsList = allowedDomains.trim()
			? allowedDomains
					.split(',')
					.map((d) => d.trim())
					.filter(Boolean)
			: null;

		const payload: Record<string, unknown> = {
			provider_type: providerType,
			display_name: displayName.trim(),
			issuer_url: issuerUrl.trim(),
			client_id: clientId.trim(),
			client_secret: clientSecret.trim(),
			tenant_id: showsTenantId && tenantId.trim() ? tenantId.trim() : null,
			allowed_email_domains: domainsList,
			is_active: true
		};

		try {
			const result = await apiJson<{ success: boolean; provider_id: string }>(
				'/setup/configure-sso',
				{
					method: 'POST',
					body: JSON.stringify(payload)
				}
			);

			onNext({
				sso: {
					provider_type: providerType,
					provider_id: result.provider_id
				}
			});
		} catch (e) {
			errorMessage =
				e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			submitting = false;
		}
	}

	function handleSkip() {
		onNext({ sso: null });
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">SSO / OIDC</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Configure an identity provider for single sign-on, or skip to set it up later.
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

		<!-- Provider Type -->
		<div>
			<label for="sso-provider-type" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Provider Type
			</label>
			<select
				id="sso-provider-type"
				bind:value={providerType}
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
			>
				{#each PROVIDER_TYPES as pt}
					<option value={pt.value}>{pt.label}</option>
				{/each}
			</select>
		</div>

		<!-- Display Name -->
		<div>
			<label for="sso-display-name" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Display Name
			</label>
			<input
				id="sso-display-name"
				type="text"
				bind:value={displayName}
				placeholder="e.g. Corporate SSO"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
		</div>

		<!-- Issuer URL -->
		<div>
			<label for="sso-issuer-url" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Issuer URL
			</label>
			<div class="flex gap-2">
				<input
					id="sso-issuer-url"
					type="url"
					bind:value={issuerUrl}
					placeholder="https://auth.example.com/realms/myorg"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
				<button
					type="button"
					onclick={handleTestConnection}
					disabled={!issuerUrl.trim() || testing}
					class="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
					title="Test Connection"
				>
					{#if testing}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Zap size={14} />
					{/if}
					Test
				</button>
			</div>

			<!-- Test result -->
			{#if testResult}
				<div class="mt-1.5 text-xs">
					{#if testResult.reachable}
						<span class="inline-flex items-center gap-1 text-success">
							<CheckCircle size={12} />
							Discovery OK
							{#if testResult.issuer}
								<span class="text-text-secondary">({testResult.issuer})</span>
							{/if}
						</span>
					{:else}
						<span class="inline-flex items-center gap-1 text-danger">
							<XCircle size={12} />
							{testResult.error || 'Unreachable'}
						</span>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Client ID + Client Secret -->
		<div class="grid grid-cols-2 gap-4">
			<div>
				<label for="sso-client-id" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Client ID
				</label>
				<input
					id="sso-client-id"
					type="text"
					bind:value={clientId}
					placeholder="firefly-desk"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>

			<div>
				<label for="sso-client-secret" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Client Secret
				</label>
				<input
					id="sso-client-secret"
					type="password"
					bind:value={clientSecret}
					placeholder="Enter client secret"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>
		</div>

		<!-- Tenant ID (Microsoft only) -->
		{#if showsTenantId}
			<div>
				<label for="sso-tenant-id" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Tenant ID <span class="text-text-secondary/60">(Microsoft only)</span>
				</label>
				<input
					id="sso-tenant-id"
					type="text"
					bind:value={tenantId}
					placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>
		{/if}

		<!-- Allowed Email Domains -->
		<div>
			<label for="sso-domains" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Allowed Email Domains <span class="text-text-secondary/60">(optional, comma-separated)</span>
			</label>
			<input
				id="sso-domains"
				type="text"
				bind:value={allowedDomains}
				placeholder="example.com, mycompany.org"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
		</div>

		<!-- Info note -->
		<p class="rounded-lg bg-surface-secondary px-4 py-3 text-xs text-text-secondary">
			You can also configure SSO later in
			<strong class="font-medium text-text-primary">Admin &gt; SSO</strong>.
			A local admin account is always available as fallback.
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

		<div class="flex items-center gap-3">
			<button
				type="button"
				onclick={handleSkip}
				class="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			>
				Skip
			</button>
			<button
				type="button"
				onclick={handleSubmit}
				disabled={!isValid || submitting}
				class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
			>
				{#if submitting}
					<Loader2 size={16} class="animate-spin" />
					Configuring...
				{:else}
					Configure SSO
					<ArrowRight size={16} />
				{/if}
			</button>
		</div>
	</div>
</div>
