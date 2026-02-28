<!--
  EmailSetupWizard.svelte - 6-step guided wizard for email channel setup.

  Walks administrators through: provider selection, credential validation,
  sender identity, deliverability DNS records, inbound webhook setup (with
  optional dev tunnel), and a final test & enable step.

  Follows the SSOWizard modal/step-indicator patterns exactly.

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
		CheckCircle,
		XCircle,
		Copy,
		Info,
		Mail,
		Key,
		ShieldCheck,
		Globe,
		Zap,
		Send,
		Eye,
		EyeOff,
		ExternalLink,
		Play,
		Square,
		AlertTriangle
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Props {
		open: boolean;
		onClose: () => void;
		onSaved: () => void;
		devMode?: boolean;
	}

	type Provider = 'resend' | 'ses';

	interface TunnelStatus {
		active: boolean;
		url: string | null;
		available: boolean;
		error: string | null;
	}

	interface ValidationResult {
		success: boolean;
		error: string | null;
		details: { domains?: string[] } | null;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { open, onClose, onSaved, devMode = false }: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = [
		'Provider',
		'Credentials',
		'Identity',
		'Deliverability',
		'Inbound',
		'Test & Enable'
	] as const;

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let saving = $state(false);
	let error = $state('');

	// Step 0: Provider
	let selectedProvider = $state<Provider | null>(null);

	// Step 1: Credentials
	let apiKey = $state('');
	let region = $state('us-east-1');
	let showApiKey = $state(false);
	let validating = $state(false);
	let validationResult = $state<ValidationResult | null>(null);

	// Step 2: Identity
	let fromAddress = $state('');
	let fromDisplayName = $state('Ember');
	let replyTo = $state('');

	// Step 4: Tunnel
	let tunnelStatus = $state<TunnelStatus>({ active: false, url: null, available: false, error: null });
	let tunnelLoading = $state(false);

	// Step 5: Test
	let testEmail = $state('');
	let testSending = $state(false);
	let testResult = $state<{ success: boolean; error?: string | null } | null>(null);
	let enableOnSave = $state(true);

	// Clipboard
	let copiedField = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	const senderDomain = $derived(fromAddress.includes('@') ? fromAddress.split('@')[1] : '');

	const webhookUrl = $derived(
		typeof window !== 'undefined'
			? `${window.location.origin}/api/email/inbound/${selectedProvider ?? 'resend'}`
			: `/api/email/inbound/${selectedProvider ?? 'resend'}`
	);

	const tunnelWebhookUrl = $derived(
		tunnelStatus.active && tunnelStatus.url
			? `${tunnelStatus.url}/api/email/inbound/${selectedProvider ?? 'resend'}`
			: null
	);

	const dmarcRecord = $derived(
		`v=DMARC1; p=none; rua=mailto:dmarc@${senderDomain || 'yourdomain.com'}`
	);

	const maskedApiKey = $derived(
		apiKey.length > 8
			? apiKey.slice(0, 4) + '•'.repeat(Math.min(apiKey.length - 8, 20)) + apiKey.slice(-4)
			: '•'.repeat(apiKey.length)
	);

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	function isStepValid(step: number): boolean {
		switch (step) {
			case 0:
				return selectedProvider !== null;
			case 1:
				if (selectedProvider === 'resend') return apiKey.trim() !== '';
				if (selectedProvider === 'ses') return region.trim() !== '';
				return false;
			case 2:
				return fromAddress.trim() !== '' && fromAddress.includes('@');
			case 3:
				return true; // Informational step
			case 4:
				return true; // Informational step
			case 5:
				return isStepValid(0) && isStepValid(1) && isStepValid(2);
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
			// Fetch tunnel status when entering Step 4
			if (currentStep === 4 && devMode) {
				fetchTunnelStatus();
			}
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
			if (step === 4 && devMode) {
				fetchTunnelStatus();
			}
		}
	}

	// -----------------------------------------------------------------------
	// Clipboard
	// -----------------------------------------------------------------------

	async function copyToClipboard(text: string, field: string) {
		try {
			await navigator.clipboard.writeText(text);
			copiedField = field;
			setTimeout(() => (copiedField = null), 2000);
		} catch {
			// Clipboard API not available
		}
	}

	// -----------------------------------------------------------------------
	// API calls
	// -----------------------------------------------------------------------

	async function validateCredentials() {
		validating = true;
		validationResult = null;

		try {
			validationResult = await apiJson<ValidationResult>('/settings/email/validate-credentials', {
				method: 'POST',
				body: JSON.stringify({
					provider: selectedProvider,
					api_key: apiKey,
					region: region
				})
			});
		} catch (e) {
			validationResult = {
				success: false,
				error: e instanceof Error ? e.message : 'Validation failed',
				details: null
			};
		} finally {
			validating = false;
		}
	}

	async function fetchTunnelStatus() {
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/settings/email/tunnel/status');
		} catch {
			// Tunnel not available
		}
	}

	async function startTunnel() {
		tunnelLoading = true;
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/settings/email/tunnel/start', {
				method: 'POST'
			});
		} catch (e) {
			tunnelStatus = {
				...tunnelStatus,
				error: e instanceof Error ? e.message : 'Failed to start tunnel'
			};
		} finally {
			tunnelLoading = false;
		}
	}

	async function stopTunnel() {
		tunnelLoading = true;
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/settings/email/tunnel/stop', {
				method: 'POST'
			});
		} catch (e) {
			tunnelStatus = {
				...tunnelStatus,
				error: e instanceof Error ? e.message : 'Failed to stop tunnel'
			};
		} finally {
			tunnelLoading = false;
		}
	}

	async function sendTestEmail() {
		if (!testEmail.trim()) return;
		testSending = true;
		testResult = null;

		try {
			testResult = await apiJson<{ success: boolean; error?: string | null }>(
				'/settings/email/test',
				{
					method: 'POST',
					body: JSON.stringify({
						to: testEmail.trim(),
						subject: 'Test from Ember Setup Wizard',
						body: 'This is a test email sent during the Email Setup Wizard. If you received this, your email configuration is working correctly.'
					})
				}
			);
		} catch (e) {
			testResult = {
				success: false,
				error: e instanceof Error ? e.message : 'Failed to send test email'
			};
		} finally {
			testSending = false;
		}
	}

	async function submit() {
		if (!isStepValid(5)) return;

		saving = true;
		error = '';

		try {
			await apiJson('/settings/email', {
				method: 'PUT',
				body: JSON.stringify({
					enabled: enableOnSave,
					from_address: fromAddress.trim(),
					from_display_name: fromDisplayName.trim(),
					reply_to: replyTo.trim(),
					provider: selectedProvider,
					provider_api_key: apiKey,
					provider_region: selectedProvider === 'ses' ? region : '',
					// Preserve defaults for fields not in the wizard
					signature_html: '',
					signature_text: '',
					email_tone: '',
					email_personality: '',
					email_instructions: '',
					auto_reply: true,
					auto_reply_delay_seconds: 30,
					max_email_length: 2000,
					include_greeting: true,
					include_sign_off: true,
					cc_mode: 'respond_all',
					cc_instructions: '',
					allowed_tool_ids: [],
					allowed_workspace_ids: []
				})
			});
			resetWizard();
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save email settings';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

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
		apiKey = '';
		region = 'us-east-1';
		showApiKey = false;
		validating = false;
		validationResult = null;
		fromAddress = '';
		fromDisplayName = 'Ember';
		replyTo = '';
		tunnelStatus = { active: false, url: null, available: false, error: null };
		tunnelLoading = false;
		testEmail = '';
		testSending = false;
		testResult = null;
		enableOnSave = true;
		saving = false;
		error = '';
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
		<div
			class="mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-surface shadow-2xl"
		>
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-border px-6 py-4">
				<h2 class="flex items-center gap-2 text-base font-semibold text-text-primary">
					<Mail size={18} class="text-accent" />
					Email Setup Wizard
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
			<div class="flex items-center gap-1 border-b border-border px-6 py-3">
				{#each STEPS as stepLabel, i}
					{@const active = i === currentStep}
					{@const complete = isStepComplete(i)}
					{@const clickable =
						i <= currentStep || (i === currentStep + 1 && isStepValid(currentStep))}

					{#if i > 0}
						<div class="h-px flex-1 {i <= currentStep ? 'bg-accent' : 'bg-border'}"></div>
					{/if}

					<button
						type="button"
						onclick={() => goToStep(i)}
						disabled={!clickable}
						class="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-medium transition-colors
							{active ? 'text-accent' : complete ? 'text-success' : 'text-text-secondary'}
							{clickable ? 'cursor-pointer hover:bg-surface-hover' : 'cursor-default opacity-50'}"
					>
						<span
							class="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold
								{active ? 'bg-accent text-white' : complete ? 'bg-success text-white' : 'bg-surface-secondary text-text-secondary'}"
						>
							{#if complete}
								<Check size={10} />
							{:else}
								{i + 1}
							{/if}
						</span>
						<span class="hidden lg:inline">{stepLabel}</span>
					</button>
				{/each}
			</div>

			<!-- Error banner -->
			{#if error}
				<div
					class="mx-6 mt-4 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
				>
					{error}
				</div>
			{/if}

			<!-- Step content -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				<!-- ============================================ -->
				<!-- Step 0: Choose Provider                       -->
				<!-- ============================================ -->
				{#if currentStep === 0}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Choose the email service provider that will handle outbound and inbound
							email for your help desk.
						</p>

						<div class="grid grid-cols-2 gap-4">
							<!-- Resend Card -->
							<button
								type="button"
								onclick={() => (selectedProvider = 'resend')}
								class="flex flex-col items-start gap-3 rounded-lg border-2 p-5 text-left transition-colors
									{selectedProvider === 'resend'
									? 'border-accent ring-2 ring-accent bg-accent/5'
									: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
							>
								<div class="flex w-full items-center justify-between">
									<span
										class="text-sm font-semibold {selectedProvider === 'resend' ? 'text-accent' : 'text-text-primary'}"
									>
										Resend
									</span>
									<Mail
										size={20}
										class={selectedProvider === 'resend' ? 'text-accent' : 'text-text-secondary'}
									/>
								</div>
								<span class="text-xs text-text-secondary">
									Modern email API built for developers. Simple setup with excellent
									deliverability.
								</span>
								<ul class="flex flex-col gap-1 text-[11px] text-text-secondary">
									<li class="flex items-center gap-1.5">
										<Check size={10} class="shrink-0 text-success" /> Built-in DKIM signing
									</li>
									<li class="flex items-center gap-1.5">
										<Check size={10} class="shrink-0 text-success" /> Webhook-based inbound
									</li>
									<li class="flex items-center gap-1.5">
										<Check size={10} class="shrink-0 text-success" /> Free tier: 3,000 emails/mo
									</li>
								</ul>
							</button>

							<!-- SES Card -->
							<button
								type="button"
								onclick={() => (selectedProvider = 'ses')}
								class="flex flex-col items-start gap-3 rounded-lg border-2 p-5 text-left transition-colors
									{selectedProvider === 'ses'
									? 'border-accent ring-2 ring-accent bg-accent/5'
									: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
							>
								<div class="flex w-full items-center justify-between">
									<span
										class="text-sm font-semibold {selectedProvider === 'ses' ? 'text-accent' : 'text-text-primary'}"
									>
										Amazon SES
									</span>
									<Globe
										size={20}
										class={selectedProvider === 'ses' ? 'text-accent' : 'text-text-secondary'}
									/>
								</div>
								<span class="text-xs text-text-secondary">
									AWS Simple Email Service. Massive throughput at extremely low cost.
								</span>
								<ul class="flex flex-col gap-1 text-[11px] text-text-secondary">
									<li class="flex items-center gap-1.5">
										<Check size={10} class="shrink-0 text-success" /> Massive send volume
									</li>
									<li class="flex items-center gap-1.5">
										<Check size={10} class="shrink-0 text-success" /> SNS-based inbound
									</li>
									<li class="flex items-center gap-1.5">
										<Check size={10} class="shrink-0 text-success" /> $0.10 per 1,000 emails
									</li>
								</ul>
							</button>
						</div>
					</div>

					<!-- ============================================ -->
					<!-- Step 1: API Credentials                      -->
					<!-- ============================================ -->
				{:else if currentStep === 1}
					<div class="grid grid-cols-[1fr_260px] gap-6">
						<!-- Form fields -->
						<div class="flex flex-col gap-4">
							<p class="text-sm text-text-secondary">
								Enter the API credentials for your
								<strong>{selectedProvider === 'resend' ? 'Resend' : 'Amazon SES'}</strong>
								account.
							</p>

							{#if selectedProvider === 'resend'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary"
										>API Key <span class="text-danger">*</span></span
									>
									<div class="flex items-center gap-1">
										<input
											type={showApiKey ? 'text' : 'password'}
											bind:value={apiKey}
											required
											placeholder="re_xxxxxxxxxxxxxxxxxxxxxxxxxx"
											class="flex-1 rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
										/>
										<button
											type="button"
											onclick={() => (showApiKey = !showApiKey)}
											class="rounded-md p-2 text-text-secondary transition-colors hover:bg-surface-hover"
											title={showApiKey ? 'Hide' : 'Show'}
										>
											{#if showApiKey}
												<EyeOff size={14} />
											{:else}
												<Eye size={14} />
											{/if}
										</button>
									</div>
								</label>
							{:else}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary"
										>AWS Region <span class="text-danger">*</span></span
									>
									<select
										bind:value={region}
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									>
										<option value="us-east-1">US East (N. Virginia)</option>
										<option value="us-west-2">US West (Oregon)</option>
										<option value="eu-west-1">EU (Ireland)</option>
										<option value="eu-central-1">EU (Frankfurt)</option>
										<option value="ap-southeast-1">Asia Pacific (Singapore)</option>
										<option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
									</select>
								</label>
							{/if}

							<!-- Validate button -->
							<div class="flex items-center gap-3">
								<button
									type="button"
									onclick={validateCredentials}
									disabled={validating || !isStepValid(1)}
									class="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface-elevated px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
								>
									{#if validating}
										<Loader2 size={14} class="animate-spin" />
										Validating...
									{:else}
										<Key size={14} />
										Validate
									{/if}
								</button>

								{#if validationResult}
									{#if validationResult.success}
										<span
											class="inline-flex items-center gap-1 text-xs font-medium text-success"
										>
											<CheckCircle size={14} />
											Credentials valid
										</span>
									{:else}
										<span
											class="inline-flex items-center gap-1 text-xs font-medium text-danger"
										>
											<XCircle size={14} />
											{validationResult.error}
										</span>
									{/if}
								{/if}
							</div>

							<!-- Verified domains -->
							{#if validationResult?.success && validationResult?.details?.domains?.length}
								<div
									class="rounded-lg border border-success/30 bg-success/5 px-3 py-2"
								>
									<span class="text-xs font-medium text-success"
										>Verified Domains:</span
									>
									<div class="mt-1 flex flex-wrap gap-1.5">
										{#each validationResult.details.domains as domain}
											<span
												class="rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
												>{domain}</span
											>
										{/each}
									</div>
								</div>
							{/if}
						</div>

						<!-- Setup guide -->
						<div
							class="flex flex-col gap-3 rounded-lg border border-border bg-surface-secondary/30 p-4"
						>
							<h4
								class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary"
							>
								<Info size={14} />
								Setup Guide
							</h4>

							{#if selectedProvider === 'resend'}
								<ol class="flex flex-col gap-2 text-xs text-text-secondary">
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">1.</span>
										Go to
										<a
											href="https://resend.com/api-keys"
											target="_blank"
											rel="noopener noreferrer"
											class="font-medium text-accent underline">resend.com/api-keys</a
										>
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">2.</span>
										Click <strong>"Create API Key"</strong>
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">3.</span>
										Give it <strong>Full access</strong> permission
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">4.</span>
										Copy the key and paste it here
									</li>
								</ol>
							{:else}
								<ol class="flex flex-col gap-2 text-xs text-text-secondary">
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">1.</span>
										Open the <strong>AWS SES Console</strong>
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">2.</span>
										Select the region closest to your users
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">3.</span>
										Verify your sending domain
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">4.</span>
										Request production access (if in sandbox)
									</li>
								</ol>
							{/if}

							<div class="border-t border-border pt-2">
								<a
									href={selectedProvider === 'resend'
										? 'https://resend.com/api-keys'
										: 'https://console.aws.amazon.com/ses/'}
									target="_blank"
									rel="noopener noreferrer"
									class="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
								>
									<ExternalLink size={10} />
									Open {selectedProvider === 'resend' ? 'Resend' : 'SES'} Dashboard
								</a>
							</div>
						</div>
					</div>

					<!-- ============================================ -->
					<!-- Step 2: Sender Identity                      -->
					<!-- ============================================ -->
				{:else if currentStep === 2}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Configure the sender identity that recipients will see on emails from your
							help desk.
						</p>

						<div class="grid grid-cols-2 gap-4">
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary"
									>From Address <span class="text-danger">*</span></span
								>
								<input
									type="email"
									bind:value={fromAddress}
									required
									placeholder="support@yourcompany.com"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary"
									>Display Name</span
								>
								<input
									type="text"
									bind:value={fromDisplayName}
									placeholder="Ember"
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>
						</div>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Reply-To Address</span
							>
							<input
								type="email"
								bind:value={replyTo}
								placeholder="Same as From address (leave empty)"
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							/>
							<span class="text-[11px] text-text-secondary"
								>Optional. Replies will be directed to this address instead of the From
								address.</span
							>
						</label>

						{#if senderDomain}
							<div class="flex items-center gap-2">
								<span class="text-xs text-text-secondary">Sending domain:</span>
								<span
									class="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent"
									>{senderDomain}</span
								>
							</div>
							{#if selectedProvider === 'resend'}
								<p class="text-[11px] text-text-secondary">
									Make sure <strong>{senderDomain}</strong> is verified in your
									<a
										href="https://resend.com/domains"
										target="_blank"
										rel="noopener noreferrer"
										class="font-medium text-accent underline">Resend domain settings</a
									>.
								</p>
							{:else}
								<p class="text-[11px] text-text-secondary">
									Make sure <strong>{senderDomain}</strong> is verified in your AWS SES
									console under Verified identities.
								</p>
							{/if}
						{/if}
					</div>

					<!-- ============================================ -->
					<!-- Step 3: Deliverability                       -->
					<!-- ============================================ -->
				{:else if currentStep === 3}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Configure these DNS records for <strong>{senderDomain || 'your domain'}</strong>
							to ensure emails reach the inbox instead of spam.
						</p>

						<!-- SPF -->
						<div class="rounded-lg border border-border bg-surface-secondary/20 p-4">
							<div class="mb-2 flex items-center gap-2">
								<span
									class="rounded bg-accent/10 px-2 py-0.5 text-[10px] font-bold text-accent"
									>SPF</span
								>
								<span class="text-xs font-medium text-text-primary"
									>Sender Policy Framework</span
								>
							</div>
							<p class="mb-2 text-[11px] text-text-secondary">
								Authorizes your email provider to send on behalf of your domain. Add as
								a <strong>TXT</strong> record on <code class="rounded bg-surface px-1">{senderDomain || 'yourdomain.com'}</code>.
							</p>
							<div class="flex items-center gap-2">
								<code
									class="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-primary"
								>
									{selectedProvider === 'resend'
										? 'v=spf1 include:amazonses.com ~all'
										: 'v=spf1 include:amazonses.com ~all'}
								</code>
								<button
									type="button"
									onclick={() =>
										copyToClipboard('v=spf1 include:amazonses.com ~all', 'spf')}
									class="shrink-0 rounded-md border border-border p-2 text-text-secondary transition-colors hover:bg-surface-hover"
								>
									{#if copiedField === 'spf'}
										<Check size={12} class="text-success" />
									{:else}
										<Copy size={12} />
									{/if}
								</button>
							</div>
						</div>

						<!-- DKIM -->
						<div class="rounded-lg border border-border bg-surface-secondary/20 p-4">
							<div class="mb-2 flex items-center gap-2">
								<span
									class="rounded bg-success/10 px-2 py-0.5 text-[10px] font-bold text-success"
									>DKIM</span
								>
								<span class="text-xs font-medium text-text-primary"
									>DomainKeys Identified Mail</span
								>
							</div>
							<p class="text-[11px] text-text-secondary">
								{#if selectedProvider === 'resend'}
									Resend handles DKIM signing automatically for verified domains.
									Verify your domain in the
									<a
										href="https://resend.com/domains"
										target="_blank"
										rel="noopener noreferrer"
										class="font-medium text-accent underline">Resend dashboard</a
									> to enable DKIM.
								{:else}
									SES provides three CNAME records for DKIM when you verify your
									domain. Add them from the SES console under <strong
										>Verified identities &gt; DKIM</strong
									>.
								{/if}
							</p>
						</div>

						<!-- DMARC -->
						<div class="rounded-lg border border-border bg-surface-secondary/20 p-4">
							<div class="mb-2 flex items-center gap-2">
								<span
									class="rounded bg-warning/10 px-2 py-0.5 text-[10px] font-bold text-warning"
									>DMARC</span
								>
								<span class="text-xs font-medium text-text-primary"
									>Domain-based Message Authentication</span
								>
							</div>
							<p class="mb-2 text-[11px] text-text-secondary">
								Tells receiving servers how to handle emails that fail SPF/DKIM. Add as
								a <strong>TXT</strong> record on
								<code class="rounded bg-surface px-1">_dmarc.{senderDomain || 'yourdomain.com'}</code>.
							</p>
							<div class="flex items-center gap-2">
								<code
									class="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-primary"
								>
									{dmarcRecord}
								</code>
								<button
									type="button"
									onclick={() => copyToClipboard(dmarcRecord, 'dmarc')}
									class="shrink-0 rounded-md border border-border p-2 text-text-secondary transition-colors hover:bg-surface-hover"
								>
									{#if copiedField === 'dmarc'}
										<Check size={12} class="text-success" />
									{:else}
										<Copy size={12} />
									{/if}
								</button>
							</div>
							<p class="mt-1.5 text-[10px] italic text-text-secondary">
								Start with p=none (monitor only), then move to p=quarantine or p=reject
								once verified.
							</p>
						</div>

						<!-- Provider dashboard link -->
						<a
							href={selectedProvider === 'resend'
								? 'https://resend.com/domains'
								: 'https://console.aws.amazon.com/ses/'}
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex w-fit items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
						>
							<ExternalLink size={12} />
							Open {selectedProvider === 'resend' ? 'Resend' : 'SES'} Domain Settings
						</a>
					</div>

					<!-- ============================================ -->
					<!-- Step 4: Inbound Setup                        -->
					<!-- ============================================ -->
				{:else if currentStep === 4}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Configure your email provider to forward inbound emails to your server via
							webhooks.
						</p>

						<!-- Webhook URL -->
						<div>
							<label class="mb-1 block text-xs font-medium text-text-secondary"
								>Webhook Endpoint</label
							>
							<div class="flex items-center gap-2">
								<code
									class="flex-1 rounded-md border border-border bg-surface-secondary/50 px-3 py-2 text-xs text-text-primary"
								>
									{webhookUrl}
								</code>
								<button
									type="button"
									onclick={() => copyToClipboard(webhookUrl, 'webhook')}
									class="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2.5 py-2 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
								>
									{#if copiedField === 'webhook'}
										<Check size={12} class="text-success" />
										Copied
									{:else}
										<Copy size={12} />
										Copy
									{/if}
								</button>
							</div>
						</div>

						<!-- Provider setup instructions -->
						<div class="rounded-md border border-border/50 bg-surface-secondary/20 p-3">
							<h3 class="mb-2 text-xs font-medium text-text-primary">
								Setup Instructions
							</h3>
							{#if selectedProvider === 'resend'}
								<ol class="flex flex-col gap-1.5 text-[11px] text-text-secondary">
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">1.</span>
										Go to
										<a
											href="https://resend.com/webhooks"
											target="_blank"
											rel="noopener noreferrer"
											class="font-medium text-accent underline">Resend Webhooks</a
										> in your dashboard.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">2.</span>
										Click <strong>"Add Webhook"</strong> and paste the endpoint URL above.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">3.</span>
										Select the <strong>"email.received"</strong> event type.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">4.</span>
										Save the webhook. Resend will forward inbound emails to your server.
									</li>
								</ol>
							{:else}
								<ol class="flex flex-col gap-1.5 text-[11px] text-text-secondary">
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">1.</span>
										In the AWS SES Console, go to <strong
											>Email Receiving &gt; Rule Sets</strong
										>.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">2.</span>
										Create a rule that sends inbound emails to an <strong
											>SNS Topic</strong
										>.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">3.</span>
										Add an <strong>HTTPS subscription</strong> to that topic with the
										endpoint URL above.
									</li>
								</ol>
							{/if}
						</div>

						<!-- Dev Tunnel Section -->
						{#if devMode && tunnelStatus.available}
							<div class="rounded-lg border border-accent/30 bg-accent/5 p-4">
								<h3
									class="mb-2 flex items-center gap-2 text-xs font-semibold text-accent"
								>
									<Zap size={14} />
									Dev Tunnel
								</h3>
								<p class="mb-3 text-[11px] text-text-secondary">
									Start an ngrok tunnel to expose your local server for testing real
									inbound emails.
								</p>

								<div class="flex items-center gap-2">
									{#if tunnelStatus.active}
										<button
											type="button"
											onclick={stopTunnel}
											disabled={tunnelLoading}
											class="inline-flex items-center gap-1.5 rounded-md border border-danger/50 bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/20 disabled:opacity-50"
										>
											{#if tunnelLoading}
												<Loader2 size={12} class="animate-spin" />
											{:else}
												<Square size={12} />
											{/if}
											Stop Tunnel
										</button>
									{:else}
										<button
											type="button"
											onclick={startTunnel}
											disabled={tunnelLoading}
											class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
										>
											{#if tunnelLoading}
												<Loader2 size={12} class="animate-spin" />
												Starting...
											{:else}
												<Play size={12} />
												Start Tunnel
											{/if}
										</button>
									{/if}

									{#if tunnelStatus.active && tunnelStatus.url}
										<span
											class="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success"
										>
											<span class="h-1.5 w-1.5 rounded-full bg-success"></span>
											Active
										</span>
									{/if}
								</div>

								{#if tunnelStatus.error}
									<p class="mt-2 text-xs text-danger">{tunnelStatus.error}</p>
								{/if}

								{#if tunnelStatus.active && tunnelWebhookUrl}
									<div class="mt-3">
										<label class="mb-1 block text-[11px] font-medium text-text-secondary"
											>Tunnel Webhook URL</label
										>
										<div class="flex items-center gap-2">
											<code
												class="flex-1 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-xs text-success"
											>
												{tunnelWebhookUrl}
											</code>
											<button
												type="button"
												onclick={() =>
													copyToClipboard(tunnelWebhookUrl!, 'tunnel-webhook')}
												class="shrink-0 rounded-md border border-border p-2 text-text-secondary transition-colors hover:bg-surface-hover"
											>
												{#if copiedField === 'tunnel-webhook'}
													<Check size={12} class="text-success" />
												{:else}
													<Copy size={12} />
												{/if}
											</button>
										</div>
										<p class="mt-1 text-[10px] text-text-secondary">
											Use this URL in your provider's webhook settings for local
											testing.
										</p>
									</div>
								{/if}
							</div>
						{:else if devMode && !tunnelStatus.available}
							<div
								class="rounded-md border border-amber-200/50 bg-amber-50/20 px-3 py-2"
							>
								<p class="text-[11px] text-amber-700">
									<strong>Dev tunnel unavailable.</strong> Install with:
									<code class="rounded bg-amber-100/50 px-1"
										>pip install 'flydesk[tunnel]'</code
									>. Requires
									<a
										href="https://ngrok.com/download"
										target="_blank"
										rel="noopener noreferrer"
										class="font-medium underline">ngrok</a
									>.
								</p>
							</div>
						{/if}
					</div>

					<!-- ============================================ -->
					<!-- Step 5: Test & Enable                        -->
					<!-- ============================================ -->
				{:else if currentStep === 5}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Review your configuration, send a test email, and enable the email
							channel.
						</p>

						<!-- Configuration summary -->
						<div
							class="rounded-lg border border-border bg-surface-secondary/30 p-4"
						>
							<h4
								class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary"
							>
								Configuration Summary
							</h4>
							<div
								class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm"
							>
								<span class="text-text-secondary">Provider:</span>
								<span class="font-medium text-text-primary"
									>{selectedProvider === 'resend' ? 'Resend' : 'Amazon SES'}</span
								>

								<span class="text-text-secondary">API Key:</span>
								<span class="font-mono text-xs text-text-primary">{maskedApiKey}</span
								>

								<span class="text-text-secondary">From:</span>
								<span class="text-text-primary"
									>{fromDisplayName} &lt;{fromAddress}&gt;</span
								>

								{#if replyTo}
									<span class="text-text-secondary">Reply-To:</span>
									<span class="text-text-primary">{replyTo}</span>
								{/if}

								<span class="text-text-secondary">Domain:</span>
								<span
									class="inline-flex w-fit rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>{senderDomain}</span
								>

								<span class="text-text-secondary">Webhook:</span>
								<span class="truncate font-mono text-xs text-text-primary"
									>{webhookUrl}</span
								>
							</div>
						</div>

						<!-- Send test email -->
						<div
							class="rounded-lg border border-border bg-surface p-4"
						>
							<h4 class="mb-2 text-xs font-semibold text-text-primary">
								Send Test Email
							</h4>
							<p class="mb-3 text-[11px] text-text-secondary">
								Send a test email to verify your configuration is working. The settings
								will be saved first.
							</p>
							<div class="flex gap-2">
								<input
									type="email"
									bind:value={testEmail}
									placeholder="your@email.com"
									class="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
								<button
									type="button"
									onclick={sendTestEmail}
									disabled={testSending || !testEmail.trim()}
									class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
								>
									{#if testSending}
										<Loader2 size={14} class="animate-spin" />
									{:else}
										<Send size={14} />
									{/if}
									Send Test
								</button>
							</div>

							{#if testResult}
								<div
									class="mt-2 rounded-md px-3 py-2 text-xs {testResult.success
										? 'border border-success/30 bg-success/5 text-success'
										: 'border border-danger/30 bg-danger/5 text-danger'}"
								>
									{#if testResult.success}
										<CheckCircle size={12} class="mr-1 inline" />
										Test email sent successfully! Check your inbox.
									{:else}
										<XCircle size={12} class="mr-1 inline" />
										{testResult.error || 'Failed to send test email'}
									{/if}
								</div>
							{/if}
						</div>

						<!-- Enable toggle -->
						<label class="flex items-center gap-3 rounded-lg border border-border bg-surface p-4">
							<input
								type="checkbox"
								bind:checked={enableOnSave}
								class="h-4 w-4 rounded border-border accent-accent"
							/>
							<div>
								<span class="text-sm font-medium text-text-primary"
									>Enable email channel</span
								>
								<p class="text-[11px] text-text-secondary">
									When enabled, the help desk will process inbound emails and can send
									outbound replies.
								</p>
							</div>
						</label>

						{#if !isStepValid(5)}
							<div
								class="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3"
							>
								<AlertTriangle size={16} class="mt-0.5 shrink-0 text-warning" />
								<p class="text-sm text-warning">
									Please complete all required fields in previous steps before saving.
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
							disabled={saving || !isStepValid(5)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if saving}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Save size={14} />
							{/if}
							Save & Enable
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
