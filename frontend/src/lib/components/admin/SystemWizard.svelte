<!--
  SystemWizard.svelte - Multi-step wizard for creating/editing external systems.

  4-step wizard: Basics, Authentication, Agent Access, Review & Create.
  Displayed as a modal overlay with step indicators, validation, and
  dynamic auth fields based on selected auth type.

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
		Shield,
		Activity
	} from 'lucide-svelte';
	import { untrack } from 'svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface AuthConfig {
		auth_type: string;
		credential_id?: string;
		token_url?: string | null;
		scopes?: string[] | null;
		auth_headers?: Record<string, string> | null;
		auth_params?: Record<string, string> | null;
	}

	interface SystemPayload {
		id: string;
		name: string;
		description: string;
		base_url: string;
		auth_config: AuthConfig;
		health_check_path: string | null;
		tags: string[];
		status: string;
		agent_enabled: boolean;
		metadata: Record<string, unknown>;
	}

	interface Credential {
		id: string;
		name: string;
		system_id: string;
		credential_type: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let {
		editingSystem = null,
		onClose,
		onSaved
	}: {
		editingSystem?: SystemPayload | null;
		onClose: () => void;
		onSaved: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Basics', 'Authentication', 'Agent Access', 'Review & Create'] as const;

	const AUTH_TYPES = [
		{ value: 'none', label: 'No Authentication' },
		{ value: 'oauth2', label: 'OAuth 2.0' },
		{ value: 'api_key', label: 'API Key' },
		{ value: 'basic', label: 'Basic Auth' },
		{ value: 'bearer', label: 'Bearer Token' },
		{ value: 'mutual_tls', label: 'Mutual TLS' }
	] as const;

	// -----------------------------------------------------------------------
	// Initial values (captured once at mount — wizard is always freshly mounted)
	// -----------------------------------------------------------------------

	// Snapshot the editing system prop at mount time. The wizard component is
	// always destroyed and re-created when opened, so this is intentional.
	const _init = untrack(() => editingSystem);
	const isEditMode = _init !== null;

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let saving = $state(false);
	let error = $state('');
	let credentials = $state<Credential[]>([]);

	// Step 1: Basics
	let name = $state(_init?.name ?? '');
	let description = $state(_init?.description ?? '');
	let baseUrl = $state(_init?.base_url ?? '');
	let status = $state(_init?.status ?? 'active');
	let tags = $state(_init?.tags?.join(', ') ?? '');
	let healthCheckPath = $state(_init?.health_check_path ?? '');

	// Step 2: Authentication
	let authType = $state(_init?.auth_config?.auth_type ?? 'none');
	let credentialId = $state(_init?.auth_config?.credential_id ?? '');
	let tokenUrl = $state(_init?.auth_config?.token_url ?? '');
	let scopes = $state(_init?.auth_config?.scopes?.join(', ') ?? '');

	// Step 3: Agent Access
	let agentEnabled = $state(_init?.agent_enabled ?? false);

	const systemId = $derived(
		isEditMode ? _init!.id : name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
	);

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	const step1Valid = $derived(name.trim() !== '' && description.trim() !== '' && baseUrl.trim() !== '');
	const step2Valid = $derived(authType === 'none' || (authType !== '' && credentialId.trim() !== ''));

	function isStepValid(step: number): boolean {
		switch (step) {
			case 0:
				return step1Valid;
			case 1:
				return step2Valid;
			case 2:
				return true; // Agent access has no required fields
			case 3:
				return step1Valid && step2Valid;
			default:
				return false;
		}
	}

	function isStepComplete(step: number): boolean {
		return step < currentStep && isStepValid(step);
	}

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadCredentials() {
		try {
			credentials = await apiJson<Credential[]>('/credentials');
		} catch {
			// Non-fatal: user can type credential ID manually
		}
	}

	$effect(() => {
		loadCredentials();
	});

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
		// Allow going to any previously visited step or the next valid step
		if (step <= currentStep || (step === currentStep + 1 && isStepValid(currentStep))) {
			currentStep = step;
		}
	}

	// -----------------------------------------------------------------------
	// Submit
	// -----------------------------------------------------------------------

	function buildPayload(): SystemPayload {
		let authConfig: AuthConfig;

		if (authType === 'none') {
			authConfig = { auth_type: 'none' };
		} else {
			authConfig = {
				auth_type: authType,
				credential_id: credentialId.trim()
			};

			if (authType === 'oauth2') {
				authConfig.token_url = tokenUrl.trim() || null;
				authConfig.scopes = scopes
					.split(',')
					.map((s) => s.trim())
					.filter(Boolean);
			}
		}

		return {
			id: systemId,
			name: name.trim(),
			description: description.trim(),
			base_url: baseUrl.trim(),
			auth_config: authConfig,
			health_check_path: healthCheckPath.trim() || null,
			tags: tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean),
			status,
			agent_enabled: agentEnabled,
			metadata: _init?.metadata ?? {}
		};
	}

	async function submit() {
		if (!isStepValid(3)) return;

		saving = true;
		error = '';

		const payload = buildPayload();

		try {
			if (isEditMode) {
				await apiJson(`/catalog/systems/${_init!.id}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/catalog/systems', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save system';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function authTypeLabel(type: string): string {
		return AUTH_TYPES.find((t) => t.value === type)?.label ?? type;
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

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
				{isEditMode ? 'Edit System' : 'New System'}
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
			<div class="mx-6 mt-4 rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
				{error}
			</div>
		{/if}

		<!-- Step content -->
		<div class="flex-1 overflow-y-auto px-6 py-5">
			<!-- Step 1: Basics -->
			{#if currentStep === 0}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Define the basic information about this external system.
					</p>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Name <span class="text-danger">*</span></span>
						<input
							type="text"
							bind:value={name}
							required
							placeholder="e.g. Salesforce CRM"
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						/>
						{#if name && systemId}
							<span class="text-xs text-text-secondary">
								System ID: <code class="rounded bg-surface-secondary px-1 py-0.5 font-mono">{systemId}</code>
							</span>
						{/if}
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Description <span class="text-danger">*</span></span>
						<textarea
							bind:value={description}
							rows={3}
							required
							placeholder="Brief description of the system and its purpose"
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						></textarea>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Base URL <span class="text-danger">*</span></span>
						<input
							type="url"
							bind:value={baseUrl}
							required
							placeholder="https://api.example.com/v1"
							class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<div class="grid grid-cols-2 gap-4">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Status</span>
							<select
								bind:value={status}
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							>
								<option value="active">Active</option>
								<option value="inactive">Inactive</option>
								<option value="degraded">Degraded</option>
							</select>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Health Check Path</span>
							<input
								type="text"
								bind:value={healthCheckPath}
								placeholder="/health or /ping"
								class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>
					</div>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
						<input
							type="text"
							bind:value={tags}
							placeholder="e.g. crm, internal, production"
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>

			<!-- Step 2: Authentication -->
			{:else if currentStep === 1}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Configure how Firefly authenticates with this system.
					</p>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Auth Type <span class="text-danger">*</span></span>
						<select
							bind:value={authType}
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						>
							{#each AUTH_TYPES as type}
								<option value={type.value}>{type.label}</option>
							{/each}
						</select>
					</label>

					{#if authType === 'none'}
						<div class="rounded-lg border border-border/50 bg-surface-hover/30 p-4">
							<p class="text-sm text-text-secondary">
								This system does not require authentication. API calls will be made without credentials.
							</p>
						</div>
					{:else}
						<!-- Dynamic fields for OAuth2 -->
						{#if authType === 'oauth2'}
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Token URL</span>
								<input
									type="url"
									bind:value={tokenUrl}
									placeholder="https://auth.example.com/oauth/token"
									class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Scopes (comma-separated)</span>
								<input
									type="text"
									bind:value={scopes}
									placeholder="e.g. read, write, admin"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>
						{/if}

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Credential <span class="text-danger">*</span></span>
							{#if credentials.length > 0}
								<select
									bind:value={credentialId}
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								>
									<option value="" disabled>Select a credential...</option>
									{#each credentials as cred}
										<option value={cred.id}>{cred.name} ({cred.credential_type})</option>
									{/each}
								</select>
							{:else}
								<input
									type="text"
									bind:value={credentialId}
									required
									placeholder="Credential ID"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							{/if}
							<span class="text-xs text-text-secondary">
								{#if authType === 'oauth2'}
									OAuth2 client credentials stored in the Credential Vault.
								{:else if authType === 'api_key'}
									API key and header configuration stored in the Credential Vault.
								{:else if authType === 'basic'}
									Basic auth username/password stored in the Credential Vault.
								{:else if authType === 'bearer'}
									Bearer token stored in the Credential Vault.
								{:else if authType === 'mutual_tls'}
									TLS certificate and key stored in the Credential Vault.
								{/if}
							</span>
						</label>
					{/if}
				</div>

			<!-- Step 3: Agent Access -->
			{:else if currentStep === 2}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Control whether the AI agent can access endpoints from this system.
					</p>

					<div class="rounded-lg border border-border bg-surface-secondary/50 p-4">
						<div class="flex items-start gap-3">
							<div class="mt-0.5">
								<Shield size={20} class="text-accent" />
							</div>
							<div class="flex-1">
								<h4 class="text-sm font-medium text-text-primary">Agent Access (Whitelist Mode)</h4>
								<p class="mt-1 text-xs text-text-secondary">
									When enabled, the agent can use endpoints from this system as tools during
									conversations. Only systems with agent access enabled are available in whitelist mode.
								</p>

								<label class="mt-3 flex items-center gap-3">
									<button
										type="button"
										role="switch"
										aria-checked={agentEnabled}
										aria-label="Toggle agent access"
										onclick={() => (agentEnabled = !agentEnabled)}
										class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors
											{agentEnabled ? 'bg-accent' : 'bg-surface-secondary'}"
									>
										<span
											class="inline-block h-4 w-4 rounded-full bg-white transition-transform
												{agentEnabled ? 'translate-x-6' : 'translate-x-1'}"
										></span>
									</button>
									<span class="text-sm font-medium text-text-primary">
										{agentEnabled ? 'Agent access enabled' : 'Agent access disabled'}
									</span>
								</label>
							</div>
						</div>
					</div>

					{#if !agentEnabled}
						<div class="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3">
							<Activity size={16} class="mt-0.5 shrink-0 text-warning" />
							<p class="text-sm text-warning">
								The agent will not be able to use any endpoints from this system in whitelist mode.
							</p>
						</div>
					{/if}
				</div>

			<!-- Step 4: Review & Create -->
			{:else if currentStep === 3}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Review the system configuration before {isEditMode ? 'updating' : 'creating'}.
					</p>

					<!-- Summary card -->
					<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
						<div class="flex flex-col gap-3">
							<!-- Basics -->
							<div>
								<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Basics
								</h4>
								<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
									<span class="text-text-secondary">Name:</span>
									<span class="font-medium text-text-primary">{name}</span>
									<span class="text-text-secondary">ID:</span>
									<span class="font-mono text-xs text-text-primary">{systemId}</span>
									<span class="text-text-secondary">Description:</span>
									<span class="text-text-primary">{description}</span>
									<span class="text-text-secondary">Base URL:</span>
									<span class="font-mono text-xs text-text-primary">{baseUrl}</span>
									<span class="text-text-secondary">Status:</span>
									<span class="text-text-primary capitalize">{status}</span>
									{#if healthCheckPath}
										<span class="text-text-secondary">Health Check:</span>
										<span class="font-mono text-xs text-text-primary">{healthCheckPath}</span>
									{/if}
									{#if tags.trim()}
										<span class="text-text-secondary">Tags:</span>
										<span class="text-text-primary">
											{tags.split(',').map((t) => t.trim()).filter(Boolean).join(', ')}
										</span>
									{/if}
								</div>
							</div>

							<hr class="border-border" />

							<!-- Authentication -->
							<div>
								<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Authentication
								</h4>
								<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
									<span class="text-text-secondary">Auth Type:</span>
									<span class="text-text-primary">{authTypeLabel(authType)}</span>
									{#if authType === 'none'}
										<span class="text-text-secondary">Credentials:</span>
										<span class="text-xs text-text-secondary italic">None required</span>
									{:else}
										<span class="text-text-secondary">Credential:</span>
										<span class="font-mono text-xs text-text-primary">{credentialId}</span>
										{#if authType === 'oauth2' && tokenUrl}
											<span class="text-text-secondary">Token URL:</span>
											<span class="font-mono text-xs text-text-primary">{tokenUrl}</span>
										{/if}
										{#if authType === 'oauth2' && scopes.trim()}
											<span class="text-text-secondary">Scopes:</span>
											<span class="text-text-primary">{scopes}</span>
										{/if}
									{/if}
								</div>
							</div>

							<hr class="border-border" />

							<!-- Agent Access -->
							<div>
								<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Agent Access
								</h4>
								<div class="flex items-center gap-2 text-sm">
									{#if agentEnabled}
										<span class="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
											<Check size={12} />
											Enabled
										</span>
										<span class="text-text-secondary">Agent can use endpoints from this system</span>
									{:else}
										<span class="inline-flex items-center gap-1 rounded-full bg-text-secondary/10 px-2 py-0.5 text-xs font-medium text-text-secondary">
											Disabled
										</span>
										<span class="text-text-secondary">Agent cannot access this system</span>
									{/if}
								</div>
							</div>
						</div>
					</div>
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
						disabled={saving || !isStepValid(3)}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						{isEditMode ? 'Update System' : 'Create System'}
					</button>
				{/if}
			</div>
		</div>
	</div>
</div>
