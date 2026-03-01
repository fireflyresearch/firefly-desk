<!--
  EmailStep.svelte -- Optional email provider setup during the wizard.

  Presents provider cards (Resend, SES, SendGrid), credential inputs,
  from-address field, and a validate button that calls
  POST /api/settings/email/validate-credentials (no auth required during
  setup). The user can skip this step entirely.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Loader2,
		CheckCircle,
		XCircle,
		ArrowLeft,
		ArrowRight,
		Eye,
		EyeOff,
		Mail
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface EmailStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: EmailStepProps = $props();

	// -----------------------------------------------------------------------
	// Provider definitions
	// -----------------------------------------------------------------------

	interface ProviderDef {
		id: string;
		name: string;
		description: string;
	}

	const providers: ProviderDef[] = [
		{ id: 'resend', name: 'Resend', description: 'Simple email API' },
		{ id: 'ses', name: 'AWS SES', description: 'Cost-effective at scale' },
		{ id: 'sendgrid', name: 'SendGrid', description: 'Popular delivery platform' }
	];

	const awsRegions = [
		'us-east-1',
		'us-east-2',
		'us-west-1',
		'us-west-2',
		'eu-west-1',
		'eu-west-2',
		'eu-central-1',
		'ap-southeast-1',
		'ap-southeast-2',
		'ap-northeast-1',
		'ap-south-1',
		'ca-central-1',
		'sa-east-1'
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let selectedProvider = $state<string | null>(null);
	let apiKey = $state('');
	let fromAddress = $state('');
	let region = $state('us-east-1');
	let showKey = $state(false);
	let validating = $state(false);
	let validateResult = $state<'success' | 'failure' | null>(null);
	let validateMessage = $state('');

	let needsApiKey = $derived(selectedProvider === 'resend' || selectedProvider === 'sendgrid');
	let needsRegion = $derived(selectedProvider === 'ses');
	let apiKeyPlaceholder = $derived(selectedProvider === 'sendgrid' ? 'SG...' : 're_...');

	let canValidate = $derived(
		selectedProvider !== null &&
			fromAddress.trim().length > 0 &&
			(!needsApiKey || apiKey.length > 0)
	);
	let canContinue = $derived(validateResult === 'success');

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function selectProvider(id: string) {
		selectedProvider = id;
		apiKey = '';
		showKey = false;
		validateResult = null;
		validateMessage = '';
		region = 'us-east-1';
	}

	async function validate() {
		if (!selectedProvider) return;
		validating = true;
		validateResult = null;
		validateMessage = '';

		try {
			const body: Record<string, string | null> = {
				provider: selectedProvider
			};
			if (needsApiKey) body.api_key = apiKey;
			if (needsRegion) body.region = region;

			const result = await apiJson<{ valid: boolean; error?: string }>(
				'/settings/email/validate-credentials',
				{
					method: 'POST',
					body: JSON.stringify(body)
				}
			);

			if (result.valid) {
				validateResult = 'success';
				validateMessage = 'Credentials validated successfully.';
			} else {
				validateResult = 'failure';
				validateMessage = result.error ?? 'Validation failed.';
			}
		} catch (e) {
			validateResult = 'failure';
			validateMessage = e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			validating = false;
		}
	}

	function handleSkip() {
		onNext({ email_provider: null });
	}

	function handleContinue() {
		onNext({
			email_provider: selectedProvider,
			email_api_key: needsApiKey ? apiKey : null,
			email_from_address: fromAddress.trim(),
			email_region: needsRegion ? region : null
		});
	}
</script>

<div class="flex h-full flex-col">
	<div class="flex items-center justify-between">
		<div>
			<h2 class="text-xl font-bold text-text-primary">Email Channel</h2>
			<p class="mt-1 text-sm text-text-secondary">
				Connect an email provider so your agent can send and receive emails. This is optional.
			</p>
		</div>
	</div>

	<!-- Skip link -->
	<button
		type="button"
		onclick={handleSkip}
		class="mt-3 self-start text-sm text-text-secondary underline decoration-dotted underline-offset-4 hover:text-text-primary"
	>
		Skip for now
	</button>

	<!-- Provider cards -->
	<div class="mt-6 grid grid-cols-3 gap-2">
		{#each providers as provider}
			<button
				type="button"
				onclick={() => selectProvider(provider.id)}
				class="rounded-lg border px-3 py-3 text-left transition-all
					{selectedProvider === provider.id
					? 'border-ember bg-ember/5 shadow-sm'
					: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
			>
				<span
					class="block text-sm font-medium {selectedProvider === provider.id
						? 'text-ember'
						: 'text-text-primary'}">{provider.name}</span
				>
				<span class="mt-0.5 block text-[11px] text-text-secondary"
					>{provider.description}</span
				>
			</button>
		{/each}
	</div>

	<!-- Configuration form -->
	{#if selectedProvider}
		<div class="mt-6 space-y-4">
			<!-- API Key (Resend / SendGrid) -->
			{#if needsApiKey}
				<div>
					<label for="email-api-key" class="mb-1.5 block text-xs font-medium text-text-secondary">
						API Key
					</label>
					<div class="relative">
						<input
							id="email-api-key"
							type={showKey ? 'text' : 'password'}
							bind:value={apiKey}
							placeholder={apiKeyPlaceholder}
							autocomplete="off"
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
						/>
						<button
							type="button"
							onclick={() => (showKey = !showKey)}
							class="absolute top-1/2 right-2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
							aria-label={showKey ? 'Hide API key' : 'Show API key'}
						>
							{#if showKey}
								<EyeOff size={16} />
							{:else}
								<Eye size={16} />
							{/if}
						</button>
					</div>
				</div>
			{/if}

			<!-- Region (SES) -->
			{#if needsRegion}
				<div>
					<label
						for="email-region"
						class="mb-1.5 block text-xs font-medium text-text-secondary"
					>
						AWS Region
					</label>
					<select
						id="email-region"
						bind:value={region}
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
					>
						{#each awsRegions as r}
							<option value={r}>{r}</option>
						{/each}
					</select>
				</div>
			{/if}

			<!-- From Address -->
			<div>
				<label
					for="email-from-address"
					class="mb-1.5 block text-xs font-medium text-text-secondary"
				>
					From Address
				</label>
				<div class="relative">
					<Mail
						size={16}
						class="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-secondary/50"
					/>
					<input
						id="email-from-address"
						type="email"
						bind:value={fromAddress}
						placeholder="ember@yourcompany.com"
						class="w-full rounded-lg border border-border bg-surface py-2 pr-3 pl-9 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
					/>
				</div>
			</div>

			<!-- Validate button -->
			<button
				type="button"
				onclick={validate}
				disabled={validating || !canValidate}
				class="btn-hover inline-flex items-center gap-2 rounded-lg bg-ember px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
			>
				{#if validating}
					<Loader2 size={16} class="animate-spin" />
					Validating...
				{:else}
					Validate
				{/if}
			</button>

			<!-- Validate result -->
			{#if validateResult === 'success'}
				<div
					class="flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 px-4 py-3 text-sm text-success"
				>
					<CheckCircle size={18} class="mt-0.5 shrink-0" />
					<span>{validateMessage}</span>
				</div>
			{:else if validateResult === 'failure'}
				<div
					class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
				>
					<XCircle size={18} class="mt-0.5 shrink-0" />
					<span>{validateMessage}</span>
				</div>
			{/if}
		</div>
	{/if}

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
			onclick={handleContinue}
			disabled={!canContinue}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
		>
			Continue
			<ArrowRight size={16} />
		</button>
	</div>
</div>
