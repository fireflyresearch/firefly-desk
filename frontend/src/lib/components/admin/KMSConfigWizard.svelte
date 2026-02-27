<!--
  KMSConfigWizard.svelte - Step-by-step wizard for KMS provider configuration.

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
		Lock,
		Cloud,
		Shield,
		Database,
		Play,
		CheckCircle,
		XCircle
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

	interface ProviderOption {
		value: string;
		label: string;
		description: string;
		icon: typeof Lock;
	}

	interface TestResult {
		success: boolean;
		message: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { open, onClose, onSaved }: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Choose Provider', 'Configuration', 'Test & Confirm'] as const;

	const PROVIDERS: ProviderOption[] = [
		{ value: 'fernet', label: 'Fernet / Local', description: 'Built-in key-based encryption', icon: Lock },
		{ value: 'aws_kms', label: 'AWS KMS', description: 'AWS Key Management Service', icon: Cloud },
		{ value: 'gcp_kms', label: 'GCP KMS', description: 'Google Cloud Key Management', icon: Cloud },
		{ value: 'azure_keyvault', label: 'Azure Key Vault', description: 'Azure Key Vault', icon: Shield },
		{ value: 'hashicorp_vault', label: 'HashiCorp Vault', description: 'HashiCorp Vault', icon: Database }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let saving = $state(false);
	let testing = $state(false);
	let loadingConfig = $state(false);
	let error = $state('');
	let testResult = $state<TestResult | null>(null);

	let selectedProvider = $state('fernet');
	let providerConfig = $state<Record<string, string>>({});

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	const step1Valid = $derived(selectedProvider !== '');

	const step2Valid = $derived(() => {
		switch (selectedProvider) {
			case 'fernet':
				return true;
			case 'aws_kms':
				return (
					(providerConfig.region ?? '').trim() !== '' &&
					(providerConfig.key_id ?? '').trim() !== '' &&
					(providerConfig.access_key_id ?? '').trim() !== '' &&
					(providerConfig.secret_access_key ?? '').trim() !== ''
				);
			case 'gcp_kms':
				return (
					(providerConfig.project_id ?? '').trim() !== '' &&
					(providerConfig.location ?? '').trim() !== '' &&
					(providerConfig.key_ring ?? '').trim() !== '' &&
					(providerConfig.key_name ?? '').trim() !== '' &&
					(providerConfig.service_account_json ?? '').trim() !== ''
				);
			case 'azure_keyvault':
				return (
					(providerConfig.vault_url ?? '').trim() !== '' &&
					(providerConfig.tenant_id ?? '').trim() !== '' &&
					(providerConfig.client_id ?? '').trim() !== '' &&
					(providerConfig.client_secret ?? '').trim() !== ''
				);
			case 'hashicorp_vault':
				return (
					(providerConfig.vault_url ?? '').trim() !== '' &&
					(providerConfig.token ?? '').trim() !== '' &&
					(providerConfig.key_name ?? '').trim() !== ''
				);
			default:
				return false;
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
	// Data loading
	// -----------------------------------------------------------------------

	async function loadCurrentConfig() {
		loadingConfig = true;
		error = '';
		try {
			const data = await apiJson<{ provider: string; config: Record<string, string> }>(
				'/settings/admin/kms'
			);
			selectedProvider = data.provider || 'fernet';
			providerConfig = data.config || {};
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load KMS configuration';
		} finally {
			loadingConfig = false;
		}
	}

	// Reset wizard state whenever opened
	$effect(() => {
		if (open) {
			currentStep = 0;
			error = '';
			testResult = null;
			saving = false;
			testing = false;
			loadCurrentConfig();
		}
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function selectProvider(value: string) {
		if (value !== selectedProvider) {
			selectedProvider = value;
			// Reset config when switching providers (unless loading from server)
			if (!loadingConfig) {
				providerConfig = value === 'hashicorp_vault'
					? { mount_path: 'secret' }
					: {};
			}
			testResult = null;
		}
	}

	async function testConnection() {
		testing = true;
		testResult = null;
		error = '';

		try {
			// Save first so the test endpoint has the latest config
			await apiJson('/settings/admin/kms', {
				method: 'PUT',
				body: JSON.stringify({ provider: selectedProvider, config: providerConfig })
			});

			const result = await apiJson<TestResult>('/settings/admin/kms/test', {
				method: 'POST'
			});
			testResult = result;
		} catch (e) {
			testResult = {
				success: false,
				message: e instanceof Error ? e.message : 'Test failed'
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
			await apiJson('/settings/admin/kms', {
				method: 'PUT',
				body: JSON.stringify({ provider: selectedProvider, config: providerConfig })
			});
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save KMS configuration';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Event handlers
	// -----------------------------------------------------------------------

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			onClose();
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
		<div class="mx-4 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl bg-surface shadow-2xl">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-border px-6 py-4">
				<h2 class="text-base font-semibold text-text-primary">
					Configure KMS Provider
				</h2>
				<button
					type="button"
					onclick={onClose}
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
				<!-- Loading state -->
				{#if loadingConfig}
					<div class="flex items-center justify-center py-12">
						<Loader2 size={24} class="animate-spin text-text-secondary" />
					</div>

				<!-- Step 1: Choose Provider -->
				{:else if currentStep === 0}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Select the Key Management Service provider for encrypting credentials.
						</p>

						<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
							{#each PROVIDERS as provider}
								{@const selected = selectedProvider === provider.value}
								<button
									type="button"
									onclick={() => selectProvider(provider.value)}
									class="flex items-start gap-3 rounded-lg border-2 px-4 py-3 text-left transition-colors
										{selected
											? 'ring-2 ring-accent bg-accent/5 border-accent'
											: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
								>
									<div class="mt-0.5 shrink-0">
										<provider.icon
											size={20}
											class={selected ? 'text-accent' : 'text-text-secondary'}
										/>
									</div>
									<div class="flex flex-col gap-0.5">
										<span class="text-sm font-medium {selected ? 'text-accent' : 'text-text-primary'}">
											{provider.label}
										</span>
										<span class="text-xs text-text-secondary">
											{provider.description}
										</span>
									</div>
								</button>
							{/each}
						</div>
					</div>

				<!-- Step 2: Provider Configuration -->
				{:else if currentStep === 1}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Configure the settings for <span class="font-medium text-text-primary">{PROVIDERS.find(p => p.value === selectedProvider)?.label}</span>.
						</p>

						<!-- Fernet -->
						{#if selectedProvider === 'fernet'}
							<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
								<div class="flex items-center gap-2 text-sm text-text-primary">
									<Lock size={16} class="text-accent" />
									<span class="font-medium">Auto-generated Fernet key</span>
								</div>
								<p class="mt-2 text-sm text-text-secondary">
									No additional configuration needed. The encryption key is automatically
									generated and managed by the application.
								</p>
								<div class="mt-3">
									<span class="text-xs font-medium text-text-secondary">Current Key</span>
									<div class="mt-1 rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-secondary">
										{providerConfig.masked_key || '****************************'}
									</div>
								</div>
							</div>

						<!-- AWS KMS -->
						{:else if selectedProvider === 'aws_kms'}
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Region <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.region}
									placeholder="e.g. us-east-1"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Key ID <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.key_id}
									placeholder="e.g. arn:aws:kms:us-east-1:123456789:key/abcd-1234"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Access Key ID <span class="text-danger">*</span></span>
								<input
									type="password"
									bind:value={providerConfig.access_key_id}
									placeholder="AWS Access Key ID"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Secret Access Key <span class="text-danger">*</span></span>
								<input
									type="password"
									bind:value={providerConfig.secret_access_key}
									placeholder="AWS Secret Access Key"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

						<!-- GCP KMS -->
						{:else if selectedProvider === 'gcp_kms'}
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Project ID <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.project_id}
									placeholder="e.g. my-gcp-project"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Location <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.location}
									placeholder="e.g. us-central1"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Key Ring <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.key_ring}
									placeholder="e.g. my-key-ring"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Key Name <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.key_name}
									placeholder="e.g. my-encryption-key"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Service Account JSON <span class="text-danger">*</span></span>
								<textarea
									bind:value={providerConfig.service_account_json}
									rows={5}
									placeholder={'{"type": "service_account", ...}'}
									class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
								></textarea>
							</label>

						<!-- Azure Key Vault -->
						{:else if selectedProvider === 'azure_keyvault'}
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Vault URL <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.vault_url}
									placeholder="e.g. https://my-vault.vault.azure.net"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Tenant ID <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.tenant_id}
									placeholder="Azure AD Tenant ID"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.client_id}
									placeholder="Azure AD Application Client ID"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
								<input
									type="password"
									bind:value={providerConfig.client_secret}
									placeholder="Azure AD Application Client Secret"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

						<!-- HashiCorp Vault -->
						{:else if selectedProvider === 'hashicorp_vault'}
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Vault URL <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.vault_url}
									placeholder="e.g. https://vault.example.com:8200"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Token <span class="text-danger">*</span></span>
								<input
									type="password"
									bind:value={providerConfig.token}
									placeholder="Vault access token"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Mount Path</span>
								<input
									type="text"
									bind:value={providerConfig.mount_path}
									placeholder="secret"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
								<span class="text-xs text-text-secondary">Defaults to "secret" if left empty.</span>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Key Name <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={providerConfig.key_name}
									placeholder="e.g. flydesk-encryption-key"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>
						{/if}
					</div>

				<!-- Step 3: Test & Confirm -->
				{:else if currentStep === 2}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Test your configuration and confirm to save.
						</p>

						<!-- Summary card -->
						<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
							<h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
								Configuration Summary
							</h4>
							<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
								<span class="text-text-secondary">Provider:</span>
								<span class="font-medium text-text-primary">
									{PROVIDERS.find(p => p.value === selectedProvider)?.label}
								</span>

								{#if selectedProvider === 'aws_kms'}
									<span class="text-text-secondary">Region:</span>
									<span class="text-text-primary">{providerConfig.region || '--'}</span>
									<span class="text-text-secondary">Key ID:</span>
									<span class="font-mono text-xs text-text-primary">{providerConfig.key_id || '--'}</span>
								{:else if selectedProvider === 'gcp_kms'}
									<span class="text-text-secondary">Project:</span>
									<span class="text-text-primary">{providerConfig.project_id || '--'}</span>
									<span class="text-text-secondary">Location:</span>
									<span class="text-text-primary">{providerConfig.location || '--'}</span>
									<span class="text-text-secondary">Key Ring:</span>
									<span class="text-text-primary">{providerConfig.key_ring || '--'}</span>
									<span class="text-text-secondary">Key Name:</span>
									<span class="text-text-primary">{providerConfig.key_name || '--'}</span>
								{:else if selectedProvider === 'azure_keyvault'}
									<span class="text-text-secondary">Vault URL:</span>
									<span class="font-mono text-xs text-text-primary">{providerConfig.vault_url || '--'}</span>
									<span class="text-text-secondary">Tenant ID:</span>
									<span class="text-text-primary">{providerConfig.tenant_id || '--'}</span>
								{:else if selectedProvider === 'hashicorp_vault'}
									<span class="text-text-secondary">Vault URL:</span>
									<span class="font-mono text-xs text-text-primary">{providerConfig.vault_url || '--'}</span>
									<span class="text-text-secondary">Mount Path:</span>
									<span class="text-text-primary">{providerConfig.mount_path || 'secret'}</span>
									<span class="text-text-secondary">Key Name:</span>
									<span class="text-text-primary">{providerConfig.key_name || '--'}</span>
								{/if}
							</div>
						</div>

						<!-- Test connection -->
						<div class="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
							<div class="flex items-center justify-between">
								<h4 class="text-sm font-medium text-text-primary">Connection Test</h4>
								<button
									type="button"
									onclick={testConnection}
									disabled={testing}
									class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
								>
									{#if testing}
										<Loader2 size={14} class="animate-spin" />
										Testing...
									{:else}
										<Play size={14} />
										Test Connection
									{/if}
								</button>
							</div>

							{#if testResult}
								<div
									class="flex items-start gap-2 rounded-md border px-4 py-3
										{testResult.success
											? 'border-success/30 bg-success/5'
											: 'border-danger/30 bg-danger/5'}"
								>
									{#if testResult.success}
										<CheckCircle size={16} class="mt-0.5 shrink-0 text-success" />
										<span class="text-sm text-success">{testResult.message}</span>
									{:else}
										<XCircle size={16} class="mt-0.5 shrink-0 text-danger" />
										<span class="text-sm text-danger">{testResult.message}</span>
									{/if}
								</div>
							{:else}
								<p class="text-xs text-text-secondary">
									Click "Test Connection" to verify your configuration before saving.
								</p>
							{/if}
						</div>

						{#if !isStepValid(2)}
							<div class="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3">
								<AlertTriangle size={16} class="mt-0.5 shrink-0 text-warning" />
								<p class="text-sm text-warning">
									Please complete all required fields before saving.
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
						onclick={onClose}
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
							Save Configuration
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
