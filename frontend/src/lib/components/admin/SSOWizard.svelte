<!--
  SSOWizard.svelte - 3-step wizard for SSO provider configuration.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		ChevronLeft,
		ChevronRight,
		Save,
		Loader2,
		Check,
		AlertTriangle,
		Shield,
		Lock,
		Globe,
		Building2,
		Key,
		Zap,
		CheckCircle,
		XCircle,
		Copy,
		Info
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Props {
		open: boolean;
		onClose: () => void;
		onSaved: () => void;
	}

	type ProviderType = 'oidc' | 'saml' | 'google' | 'microsoft' | 'okta' | 'auth0';

	interface ProviderOption {
		value: ProviderType;
		label: string;
		description: string;
		icon: typeof Shield;
	}

	interface TestResult {
		reachable: boolean;
		issuer: string | null;
		authorization_endpoint: string | null;
		token_endpoint: string | null;
		error: string | null;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { open, onClose, onSaved }: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Choose Provider', 'Configuration', 'Test & Save'] as const;

	const PROVIDERS: ProviderOption[] = [
		{ value: 'oidc', label: 'Generic OIDC', description: 'Any OpenID Connect provider', icon: Shield },
		{ value: 'saml', label: 'SAML 2.0', description: 'SAML-based identity provider', icon: Lock },
		{ value: 'google', label: 'Google Workspace', description: 'Google OAuth / Workspace', icon: Globe },
		{ value: 'microsoft', label: 'Microsoft Entra ID', description: 'Azure AD / Microsoft', icon: Building2 },
		{ value: 'okta', label: 'Okta', description: 'Okta identity platform', icon: Key },
		{ value: 'auth0', label: 'Auth0', description: 'Auth0 by Okta', icon: Zap }
	];

	const NAME_ID_FORMATS = [
		{ value: 'email', label: 'Email Address' },
		{ value: 'persistent', label: 'Persistent' },
		{ value: 'transient', label: 'Transient' }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let selectedProvider = $state<ProviderType | null>(null);
	let saving = $state(false);
	let testing = $state(false);
	let error = $state('');
	let testResult = $state<TestResult | null>(null);
	let copiedRedirectUri = $state(false);

	let formData = $state({
		display_name: '',
		issuer_url: '',
		client_id: '',
		client_secret: '',
		scopes: 'openid email profile',
		entity_id: '',
		sso_url: '',
		certificate: '',
		name_id_format: 'email',
		allowed_domains: '',
		tenant_id: '',
		okta_domain: '',
		auth0_domain: ''
	});

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	const redirectUri = $derived(
		typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '/auth/callback'
	);

	const step1Valid = $derived(selectedProvider !== null);

	const step2Valid = $derived(() => {
		if (!selectedProvider) return false;
		switch (selectedProvider) {
			case 'oidc':
				return (
					formData.display_name.trim() !== '' &&
					formData.issuer_url.trim() !== '' &&
					formData.client_id.trim() !== '' &&
					formData.client_secret.trim() !== ''
				);
			case 'saml':
				return (
					formData.display_name.trim() !== '' &&
					formData.entity_id.trim() !== '' &&
					formData.sso_url.trim() !== '' &&
					formData.certificate.trim() !== ''
				);
			case 'google':
				return (
					formData.display_name.trim() !== '' &&
					formData.client_id.trim() !== '' &&
					formData.client_secret.trim() !== ''
				);
			case 'microsoft':
				return (
					formData.display_name.trim() !== '' &&
					formData.tenant_id.trim() !== '' &&
					formData.client_id.trim() !== '' &&
					formData.client_secret.trim() !== ''
				);
			case 'okta':
				return (
					formData.display_name.trim() !== '' &&
					formData.okta_domain.trim() !== '' &&
					formData.client_id.trim() !== '' &&
					formData.client_secret.trim() !== ''
				);
			case 'auth0':
				return (
					formData.display_name.trim() !== '' &&
					formData.auth0_domain.trim() !== '' &&
					formData.client_id.trim() !== '' &&
					formData.client_secret.trim() !== ''
				);
			default:
				return false;
		}
	});

	const setupNotes = $derived(() => {
		switch (selectedProvider) {
			case 'oidc':
				return 'Configure your OpenID Connect provider with the redirect URI shown above. Ensure the provider supports the Authorization Code flow.';
			case 'saml':
				return 'Upload the SP metadata or manually configure the ACS URL in your SAML Identity Provider. The certificate should be the Base64-encoded X.509 certificate from your IdP.';
			case 'google':
				return 'Enable Google OAuth in the Google Cloud Console. Create OAuth 2.0 credentials under APIs & Services > Credentials and add the redirect URI.';
			case 'microsoft':
				return 'Register an application in Microsoft Entra ID (Azure AD). Under Authentication, add the redirect URI as a Web platform redirect. The Tenant ID is found in the Azure portal under Entra ID > Overview.';
			case 'okta':
				return 'Create a new OIDC Web Application in the Okta Admin Console. Add the redirect URI under Sign-in redirect URIs. The Okta Domain is your organization URL (e.g., dev-123456.okta.com).';
			case 'auth0':
				return 'Create a Regular Web Application in the Auth0 Dashboard. Add the redirect URI under Application Settings > Allowed Callback URLs. The Auth0 Domain is found in Settings (e.g., your-tenant.auth0.com).';
			default:
				return '';
		}
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	function isStepValid(step: number): boolean {
		switch (step) {
			case 0:
				return step1Valid;
			case 1:
				return step2Valid();
			case 2:
				return step1Valid && step2Valid();
			default:
				return false;
		}
	}

	function isStepComplete(step: number): boolean {
		return step < currentStep && isStepValid(step);
	}

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	function goNext() {
		if (currentStep < STEPS.length - 1 && isStepValid(currentStep)) {
			currentStep += 1;
		}
	}

	function goPrev() {
		if (currentStep > 0) {
			currentStep -= 1;
		}
	}

	function goToStep(step: number) {
		if (step <= currentStep || (step === currentStep + 1 && isStepValid(currentStep))) {
			currentStep = step;
		}
	}

	// -----------------------------------------------------------------------
	// Provider selection
	// -----------------------------------------------------------------------

	function selectProvider(provider: ProviderType) {
		selectedProvider = provider;
		// Set default display names
		switch (provider) {
			case 'google':
				formData.display_name = formData.display_name || 'Google';
				break;
			case 'microsoft':
				formData.display_name = formData.display_name || 'Microsoft';
				break;
			case 'okta':
				formData.display_name = formData.display_name || 'Okta';
				break;
			case 'auth0':
				formData.display_name = formData.display_name || 'Auth0';
				break;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function buildPayload(): Record<string, unknown> {
		const base: Record<string, unknown> = {
			provider_type: selectedProvider,
			display_name: formData.display_name.trim(),
			is_active: true
		};

		switch (selectedProvider) {
			case 'oidc':
				return {
					...base,
					issuer_url: formData.issuer_url.trim(),
					client_id: formData.client_id.trim(),
					client_secret: formData.client_secret,
					scopes: formData.scopes
						.split(',')
						.map((s) => s.trim())
						.filter(Boolean)
				};
			case 'saml':
				return {
					...base,
					entity_id: formData.entity_id.trim(),
					sso_url: formData.sso_url.trim(),
					certificate: formData.certificate.trim(),
					name_id_format: formData.name_id_format
				};
			case 'google':
				return {
					...base,
					client_id: formData.client_id.trim(),
					client_secret: formData.client_secret,
					allowed_email_domains: formData.allowed_domains
						.split(',')
						.map((d) => d.trim())
						.filter(Boolean)
				};
			case 'microsoft':
				return {
					...base,
					tenant_id: formData.tenant_id.trim(),
					client_id: formData.client_id.trim(),
					client_secret: formData.client_secret
				};
			case 'okta':
				return {
					...base,
					okta_domain: formData.okta_domain.trim(),
					client_id: formData.client_id.trim(),
					client_secret: formData.client_secret
				};
			case 'auth0':
				return {
					...base,
					auth0_domain: formData.auth0_domain.trim(),
					client_id: formData.client_id.trim(),
					client_secret: formData.client_secret
				};
			default:
				return base;
		}
	}

	async function copyRedirectUri() {
		try {
			await navigator.clipboard.writeText(redirectUri);
			copiedRedirectUri = true;
			setTimeout(() => (copiedRedirectUri = false), 2000);
		} catch {
			// Clipboard API not available
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			handleClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			handleClose();
		}
	}

	function handleClose() {
		resetWizard();
		onClose();
	}

	function resetWizard() {
		currentStep = 0;
		selectedProvider = null;
		saving = false;
		testing = false;
		error = '';
		testResult = null;
		formData = {
			display_name: '',
			issuer_url: '',
			client_id: '',
			client_secret: '',
			scopes: 'openid email profile',
			entity_id: '',
			sso_url: '',
			certificate: '',
			name_id_format: 'email',
			allowed_domains: '',
			tenant_id: '',
			okta_domain: '',
			auth0_domain: ''
		};
	}

	// -----------------------------------------------------------------------
	// API calls
	// -----------------------------------------------------------------------

	async function testConnection() {
		testing = true;
		testResult = null;
		error = '';

		try {
			const payload = buildPayload();
			testResult = await apiJson<TestResult>('/admin/sso/providers/test', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
		} catch (e) {
			testResult = {
				reachable: false,
				issuer: null,
				authorization_endpoint: null,
				token_endpoint: null,
				error: e instanceof Error ? e.message : 'Connection test failed'
			};
		} finally {
			testing = false;
		}
	}

	async function submit() {
		if (!isStepValid(2)) return;

		saving = true;
		error = '';

		try {
			const payload = buildPayload();
			await apiJson('/admin/sso/providers', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			resetWizard();
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save provider';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- Modal backdrop -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		role="presentation"
		onclick={handleBackdropClick}
	>
		<!-- Modal content -->
		<div class="mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-surface shadow-2xl">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-border px-6 py-4">
				<h2 class="text-base font-semibold text-text-primary">
					Configure SSO Provider
				</h2>
				<button
					type="button"
					onclick={handleClose}
					class="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Step indicators -->
			<div class="flex items-center gap-2 border-b border-border px-6 py-3">
				{#each STEPS as stepLabel, i}
					{@const active = i === currentStep}
					{@const complete = isStepComplete(i)}
					{@const clickable = i <= currentStep || (i === currentStep + 1 && isStepValid(currentStep))}

					{#if i > 0}
						<div class="h-px flex-1 {i <= currentStep ? 'bg-accent' : 'bg-border'}"></div>
					{/if}

					<button
						type="button"
						onclick={() => goToStep(i)}
						disabled={!clickable}
						class="flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium transition-colors
							{active ? 'text-accent' : complete ? 'text-success' : 'text-text-secondary'}
							{clickable ? 'cursor-pointer hover:bg-surface-hover' : 'cursor-default opacity-50'}"
					>
						<span
							class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold
								{active ? 'bg-accent text-white' : complete ? 'bg-success text-white' : 'bg-surface-secondary text-text-secondary'}"
						>
							{#if complete}
								<Check size={12} />
							{:else}
								{i + 1}
							{/if}
						</span>
						<span class="hidden sm:inline">{stepLabel}</span>
					</button>
				{/each}
			</div>

			<!-- Error banner -->
			{#if error}
				<div class="mx-6 mt-4 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
					{error}
				</div>
			{/if}

			<!-- Step content -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				<!-- Step 1: Choose Provider -->
				{#if currentStep === 0}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Select the identity provider you want to configure for single sign-on.
						</p>

						<div class="grid grid-cols-3 gap-3">
							{#each PROVIDERS as provider}
								{@const selected = selectedProvider === provider.value}
								<button
									type="button"
									onclick={() => selectProvider(provider.value)}
									class="flex flex-col items-center gap-2 rounded-lg border-2 px-4 py-4 text-center transition-colors
										{selected
											? 'ring-2 ring-accent bg-accent/5 border-accent'
											: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
								>
									<provider.icon size={24} class={selected ? 'text-accent' : 'text-text-secondary'} />
									<span class="text-sm font-medium {selected ? 'text-accent' : 'text-text-primary'}">
										{provider.label}
									</span>
									<span class="text-xs text-text-secondary">
										{provider.description}
									</span>
								</button>
							{/each}
						</div>
					</div>

				<!-- Step 2: Configuration -->
				{:else if currentStep === 1}
					<div class="grid grid-cols-[1fr_280px] gap-6">
						<!-- Form fields -->
						<div class="flex flex-col gap-4">
							<p class="text-sm text-text-secondary">
								Enter the configuration details for your
								{PROVIDERS.find((p) => p.value === selectedProvider)?.label ?? ''} provider.
							</p>

							<!-- Common: Display Name -->
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Display Name <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={formData.display_name}
									required
									placeholder="e.g. Corporate SSO"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<!-- OIDC fields -->
							{#if selectedProvider === 'oidc'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Issuer URL <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.issuer_url}
										required
										placeholder="https://auth.example.com/realms/myorg"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.client_id}
										required
										placeholder="firefly-desk"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
									<input
										type="password"
										bind:value={formData.client_secret}
										required
										placeholder="Enter client secret"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Scopes</span>
									<input
										type="text"
										bind:value={formData.scopes}
										placeholder="openid email profile"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
									<span class="text-xs text-text-secondary">Space or comma-separated list of scopes.</span>
								</label>

							<!-- SAML fields -->
							{:else if selectedProvider === 'saml'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Entity ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.entity_id}
										required
										placeholder="https://idp.example.com/metadata"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">SSO URL <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.sso_url}
										required
										placeholder="https://idp.example.com/sso/saml"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Certificate <span class="text-danger">*</span></span>
									<textarea
										bind:value={formData.certificate}
										required
										rows={4}
										placeholder="Paste the Base64-encoded X.509 certificate from your IdP..."
										class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
									></textarea>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Name ID Format</span>
									<select
										bind:value={formData.name_id_format}
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									>
										{#each NAME_ID_FORMATS as fmt}
											<option value={fmt.value}>{fmt.label}</option>
										{/each}
									</select>
								</label>

							<!-- Google fields -->
							{:else if selectedProvider === 'google'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.client_id}
										required
										placeholder="123456789.apps.googleusercontent.com"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
									<input
										type="password"
										bind:value={formData.client_secret}
										required
										placeholder="Enter client secret"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Allowed Domains</span>
									<input
										type="text"
										bind:value={formData.allowed_domains}
										placeholder="example.com, mycompany.org"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
									<span class="text-xs text-text-secondary">Comma-separated list of allowed email domains.</span>
								</label>

							<!-- Microsoft fields -->
							{:else if selectedProvider === 'microsoft'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Tenant ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.tenant_id}
										required
										placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.client_id}
										required
										placeholder="Application (client) ID"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
									<input
										type="password"
										bind:value={formData.client_secret}
										required
										placeholder="Enter client secret"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

							<!-- Okta fields -->
							{:else if selectedProvider === 'okta'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Okta Domain <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.okta_domain}
										required
										placeholder="dev-123456.okta.com"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.client_id}
										required
										placeholder="0oa1bcdef2GhIjKlMn3o"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
									<input
										type="password"
										bind:value={formData.client_secret}
										required
										placeholder="Enter client secret"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

							<!-- Auth0 fields -->
							{:else if selectedProvider === 'auth0'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Auth0 Domain <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.auth0_domain}
										required
										placeholder="your-tenant.auth0.com"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.client_id}
										required
										placeholder="AbCdEf0GhIjKlMnOpQrSt"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
									<input
										type="password"
										bind:value={formData.client_secret}
										required
										placeholder="Enter client secret"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>
							{/if}
						</div>

						<!-- Setup Instructions panel -->
						<div class="flex flex-col gap-3 rounded-lg border border-border bg-surface-secondary/30 p-4">
							<h4 class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
								<Info size={14} />
								Setup Instructions
							</h4>

							<!-- Redirect URI -->
							<div class="flex flex-col gap-1.5">
								<span class="text-xs font-medium text-text-secondary">Redirect URI</span>
								<div class="flex items-center gap-1">
									<code class="flex-1 break-all rounded bg-surface px-2 py-1.5 font-mono text-xs text-text-primary">
										{redirectUri}
									</code>
									<button
										type="button"
										onclick={copyRedirectUri}
										class="shrink-0 rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
										title="Copy redirect URI"
									>
										{#if copiedRedirectUri}
											<Check size={14} class="text-success" />
										{:else}
											<Copy size={14} />
										{/if}
									</button>
								</div>
								<span class="text-[10px] text-text-secondary">
									Configure this URI in your identity provider.
								</span>
							</div>

							<!-- Provider-specific notes -->
							{#if setupNotes()}
								<div class="border-t border-border pt-3">
									<span class="text-xs font-medium text-text-secondary">Notes</span>
									<p class="mt-1 text-xs leading-relaxed text-text-secondary">
										{setupNotes()}
									</p>
								</div>
							{/if}
						</div>
					</div>

				<!-- Step 3: Test & Save -->
				{:else if currentStep === 2}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Test the connection to your identity provider before saving the configuration.
						</p>

						<!-- Configuration summary -->
						<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
							<h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
								Configuration Summary
							</h4>
							<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
								<span class="text-text-secondary">Provider:</span>
								<span class="font-medium text-text-primary">
									{PROVIDERS.find((p) => p.value === selectedProvider)?.label ?? selectedProvider}
								</span>
								<span class="text-text-secondary">Display Name:</span>
								<span class="text-text-primary">{formData.display_name}</span>

								{#if selectedProvider === 'oidc'}
									<span class="text-text-secondary">Issuer URL:</span>
									<span class="font-mono text-xs text-text-primary">{formData.issuer_url}</span>
									<span class="text-text-secondary">Client ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.client_id}</span>
									<span class="text-text-secondary">Scopes:</span>
									<span class="text-xs text-text-primary">{formData.scopes}</span>
								{:else if selectedProvider === 'saml'}
									<span class="text-text-secondary">Entity ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.entity_id}</span>
									<span class="text-text-secondary">SSO URL:</span>
									<span class="font-mono text-xs text-text-primary">{formData.sso_url}</span>
									<span class="text-text-secondary">Name ID Format:</span>
									<span class="text-xs text-text-primary">
										{NAME_ID_FORMATS.find((f) => f.value === formData.name_id_format)?.label ?? formData.name_id_format}
									</span>
								{:else if selectedProvider === 'google'}
									<span class="text-text-secondary">Client ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.client_id}</span>
									{#if formData.allowed_domains.trim()}
										<span class="text-text-secondary">Allowed Domains:</span>
										<span class="text-xs text-text-primary">{formData.allowed_domains}</span>
									{/if}
								{:else if selectedProvider === 'microsoft'}
									<span class="text-text-secondary">Tenant ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.tenant_id}</span>
									<span class="text-text-secondary">Client ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.client_id}</span>
								{:else if selectedProvider === 'okta'}
									<span class="text-text-secondary">Okta Domain:</span>
									<span class="font-mono text-xs text-text-primary">{formData.okta_domain}</span>
									<span class="text-text-secondary">Client ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.client_id}</span>
								{:else if selectedProvider === 'auth0'}
									<span class="text-text-secondary">Auth0 Domain:</span>
									<span class="font-mono text-xs text-text-primary">{formData.auth0_domain}</span>
									<span class="text-text-secondary">Client ID:</span>
									<span class="font-mono text-xs text-text-primary">{formData.client_id}</span>
								{/if}
							</div>
						</div>

						<!-- Test connection -->
						<div class="flex flex-col gap-3">
							<button
								type="button"
								onclick={testConnection}
								disabled={testing}
								class="inline-flex w-fit items-center gap-1.5 rounded-md border border-border bg-surface-elevated px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
							>
								{#if testing}
									<Loader2 size={14} class="animate-spin" />
									Testing Connection...
								{:else}
									<Zap size={14} />
									Test Connection
								{/if}
							</button>

							<!-- Test result -->
							{#if testResult}
								<div
									class="rounded-lg border p-4 {testResult.reachable
										? 'border-success/30 bg-success/5'
										: 'border-danger/30 bg-danger/5'}"
								>
									<div class="flex items-start gap-2">
										{#if testResult.reachable}
											<CheckCircle size={16} class="mt-0.5 shrink-0 text-success" />
											<div class="flex flex-col gap-1">
												<span class="text-sm font-medium text-success">Connection successful</span>
												{#if testResult.issuer}
													<span class="text-xs text-text-secondary">
														Issuer: <code class="rounded bg-surface px-1 py-0.5 font-mono">{testResult.issuer}</code>
													</span>
												{/if}
												{#if testResult.authorization_endpoint}
													<span class="text-xs text-text-secondary">
														Authorization: <code class="rounded bg-surface px-1 py-0.5 font-mono">{testResult.authorization_endpoint}</code>
													</span>
												{/if}
												{#if testResult.token_endpoint}
													<span class="text-xs text-text-secondary">
														Token: <code class="rounded bg-surface px-1 py-0.5 font-mono">{testResult.token_endpoint}</code>
													</span>
												{/if}
											</div>
										{:else}
											<XCircle size={16} class="mt-0.5 shrink-0 text-danger" />
											<div class="flex flex-col gap-1">
												<span class="text-sm font-medium text-danger">Connection failed</span>
												{#if testResult.error}
													<span class="text-xs text-danger/80">{testResult.error}</span>
												{/if}
											</div>
										{/if}
									</div>
								</div>
							{/if}
						</div>

						{#if !isStepValid(2)}
							<div class="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3">
								<AlertTriangle size={16} class="mt-0.5 shrink-0 text-warning" />
								<p class="text-sm text-warning">
									Please complete all required fields in the previous step before saving.
								</p>
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Footer navigation -->
			<div class="flex items-center justify-between border-t border-border px-6 py-4">
				<div>
					{#if currentStep > 0}
						<button
							type="button"
							onclick={goPrev}
							class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
						>
							<ChevronLeft size={14} />
							Back
						</button>
					{/if}
				</div>

				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={handleClose}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>

					{#if currentStep < STEPS.length - 1}
						<button
							type="button"
							onclick={goNext}
							disabled={!isStepValid(currentStep)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							Next
							<ChevronRight size={14} />
						</button>
					{:else}
						<button
							type="button"
							onclick={submit}
							disabled={saving || !isStepValid(2)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if saving}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Save size={14} />
							{/if}
							Save Provider
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
