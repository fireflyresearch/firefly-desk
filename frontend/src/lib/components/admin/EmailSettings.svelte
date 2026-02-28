<!--
  EmailSettings.svelte - Admin panel for email channel configuration.

  Allows administrators to configure the email provider, identity, signature,
  behaviour settings, CC handling, inbound webhooks, and send test emails.

  Organized into seven subtabs: General, Providers, Identity, Signature, Behaviour, Outbound, Inbound.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Save,
		Loader2,
		RotateCcw,
		Mail,
		Send,
		CheckCircle,
		AlertCircle,
		Clock,
		MessageSquare,
		Users,
		Settings,
		Signature,
		CircleUser,
		SlidersHorizontal,
		Eye,
		Pencil,
		UserCheck,
		Zap,
		Inbox,
		ShieldCheck,
		Globe,
		Copy,
		ExternalLink,
		Code,
		Sparkles,
		Radio,
		Power,
		PowerOff,
		ImagePlus,
		Trash2,
		Upload,
		Unplug,
		ChevronDown,
		ChevronRight,
		Package,
		ArrowUpRight,
		Cloud
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import CodeEditor from '$lib/components/shared/CodeEditor.svelte';
	import EmailSetupWizard from './EmailSetupWizard.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface EmailSettingsData {
		enabled: boolean;
		from_address: string;
		from_display_name: string;
		reply_to: string;
		provider: string;
		provider_api_key: string;
		provider_region: string;
		signature_html: string;
		signature_text: string;
		signature_image_url: string;
		email_tone: string;
		email_personality: string;
		email_instructions: string;
		auto_reply: boolean;
		auto_reply_delay_seconds: number;
		max_email_length: number;
		include_greeting: boolean;
		include_sign_off: boolean;
		cc_mode: string;
		cc_instructions: string;
		allowed_tool_ids: string[];
		allowed_workspace_ids: string[];
	}

	interface EmailStatus {
		enabled: boolean;
		provider: string;
		from_address: string;
		configured: boolean;
	}

	interface ProviderInfo {
		id: string;
		name: string;
		description: string;
		icon: typeof Mail;
		features: string[];
	}

	// -----------------------------------------------------------------------
	// Defaults
	// -----------------------------------------------------------------------

	const EMAIL_DEFAULTS: EmailSettingsData = {
		enabled: false,
		from_address: 'ember@flydesk.ai',
		from_display_name: 'Ember',
		reply_to: '',
		provider: 'resend',
		provider_api_key: '',
		provider_region: '',
		signature_html: '',
		signature_text: '',
		signature_image_url: '',
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
		allowed_workspace_ids: [],
	};

	const PROVIDERS: ProviderInfo[] = [
		{
			id: 'resend',
			name: 'Resend',
			description: 'Modern email API with excellent deliverability and developer experience.',
			icon: Send,
			features: ['Automatic DKIM', 'Webhook support', 'Inbound email'],
		},
		{
			id: 'ses',
			name: 'Amazon SES',
			description: 'Scalable, cost-effective email service from AWS infrastructure.',
			icon: Cloud,
			features: ['High volume', 'SNS integration', 'Custom configuration'],
		},
	];

	// -----------------------------------------------------------------------
	// Tabs
	// -----------------------------------------------------------------------

	type TabId = 'general' | 'providers' | 'identity' | 'signature' | 'behaviour' | 'outbound' | 'inbound';
	let activeTab = $state<TabId>('general');

	const tabs: { id: TabId; label: string; icon: any }[] = [
		{ id: 'general', label: 'General', icon: Mail },
		{ id: 'providers', label: 'Providers', icon: Package },
		{ id: 'identity', label: 'Identity', icon: CircleUser },
		{ id: 'signature', label: 'Signature', icon: Signature },
		{ id: 'behaviour', label: 'Behaviour', icon: SlidersHorizontal },
		{ id: 'outbound', label: 'Outbound', icon: ArrowUpRight },
		{ id: 'inbound', label: 'Inbound', icon: Inbox },
	];

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		devMode?: boolean;
	}

	let { devMode = false }: Props = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');
	let showWizard = $state(false);
	let showDisconnectModal = $state(false);
	let disconnecting = $state(false);

	let testEmail = $state('');
	let testSending = $state(false);
	let testResult = $state('');
	let testError = $state('');

	let validating = $state(false);
	let validateResult = $state<{ success: boolean; error?: string; details?: any } | null>(null);

	let status = $state<EmailStatus | null>(null);

	// Provider configuration state
	let configuringProvider = $state<string | null>(null);

	// Inbound simulation state
	let simFromAddress = $state('');
	let simSubject = $state('Test inbound email');
	let simulating = $state(false);
	let simResult = $state<any>(null);

	// Identity check state
	let identityEmail = $state('');
	let checkingIdentity = $state(false);
	let identityResult = $state<any>(null);

	// Email users
	let emailUsers = $state<Array<{id: string; username: string; email: string; display_name: string; is_active: boolean}>>([]);

	// Webhook URL state
	let webhookCopied = $state(false);

	// Tunnel state
	interface TunnelStatus {
		active: boolean;
		url: string | null;
		available: boolean;
		error: string | null;
	}
	let tunnelStatus = $state<TunnelStatus>({ active: false, url: null, available: false, error: null });
	let tunnelLoading = $state(false);
	let tunnelUrlCopied = $state(false);
	let tunnelWebhookCopied = $state(false);

	// Form state -- matches EmailSettings backend model
	let form = $state<EmailSettingsData>({ ...EMAIL_DEFAULTS });

	// Signature tab state
	let signatureEditing = $state(false);
	let resettingSignature = $state(false);
	let uploadingImage = $state(false);
	let imageUploadError = $state('');

	// Deliverability collapsible
	let dnsExpanded = $state(false);

	// Signature preview
	let signaturePreviewHtml = $derived(
		form.signature_html
			? `<!DOCTYPE html><html><head><style>body{margin:0;padding:12px 16px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;}</style></head><body>${form.signature_html}</body></html>`
			: ''
	);

	function resizePreviewIframe(event: Event) {
		const iframe = event.target as HTMLIFrameElement;
		try {
			const body = iframe.contentDocument?.body;
			if (body) {
				iframe.style.height = body.scrollHeight + 'px';
			}
		} catch {
			iframe.style.height = '120px';
		}
	}

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let delayLabel = $derived(
		form.auto_reply_delay_seconds < 60
			? `${form.auto_reply_delay_seconds}s`
			: `${Math.floor(form.auto_reply_delay_seconds / 60)}m ${form.auto_reply_delay_seconds % 60}s`
	);

	let activeProvider = $derived(PROVIDERS.find(p => p.id === form.provider));
	let isConfigured = $derived(status?.configured ?? false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadSettings() {
		loading = true;
		error = '';
		try {
			const [settings, st] = await Promise.all([
				apiJson<EmailSettingsData>('/settings/email'),
				apiJson<EmailStatus>('/settings/email/status'),
			]);
			form = { ...EMAIL_DEFAULTS, ...settings };
			status = st;

			loadEmailUsers();
			loadTunnelStatus();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load email settings';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadSettings();
	});

	// -----------------------------------------------------------------------
	// Save
	// -----------------------------------------------------------------------

	async function saveSettings() {
		saving = true;
		error = '';
		successMsg = '';
		try {
			await apiJson('/settings/email', {
				method: 'PUT',
				body: JSON.stringify(form),
			});
			status = await apiJson<EmailStatus>('/settings/email/status');
			successMsg = 'Email settings saved successfully.';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save email settings';
		} finally {
			saving = false;
		}
	}

	function resetToDefaults() {
		form = { ...EMAIL_DEFAULTS };
	}

	// -----------------------------------------------------------------------
	// Disconnect
	// -----------------------------------------------------------------------

	async function disconnectEmail() {
		disconnecting = true;
		try {
			await apiJson('/settings/email/disconnect', { method: 'POST' });
			showDisconnectModal = false;
			configuringProvider = null;
			await loadSettings();
			successMsg = 'Email channel disconnected.';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to disconnect';
		} finally {
			disconnecting = false;
		}
	}

	// -----------------------------------------------------------------------
	// Provider configuration
	// -----------------------------------------------------------------------

	function selectProvider(providerId: string) {
		form.provider = providerId;
		configuringProvider = providerId;
		validateResult = null;
	}

	function cancelProviderConfig() {
		configuringProvider = null;
		validateResult = null;
	}

	// -----------------------------------------------------------------------
	// Signature
	// -----------------------------------------------------------------------

	async function resetSignatureToDefault() {
		resettingSignature = true;
		try {
			const res = await apiJson<{ signature_html: string }>('/settings/email/default-signature');
			form.signature_html = res.signature_html;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load default signature';
		} finally {
			resettingSignature = false;
		}
	}

	// -----------------------------------------------------------------------
	// Connection validation
	// -----------------------------------------------------------------------

	async function validateConnection() {
		validating = true;
		validateResult = null;
		try {
			const res = await apiJson<{ success: boolean; error?: string; details?: any }>('/settings/email/validate', {
				method: 'POST',
			});
			validateResult = res;
		} catch (e) {
			validateResult = { success: false, error: e instanceof Error ? e.message : 'Connection failed' };
		} finally {
			validating = false;
		}
	}

	// -----------------------------------------------------------------------
	// Test email
	// -----------------------------------------------------------------------

	async function sendTestEmail() {
		if (!testEmail.trim()) return;
		testSending = true;
		testResult = '';
		testError = '';
		try {
			await apiJson('/settings/email/test', {
				method: 'POST',
				body: JSON.stringify({ to: testEmail.trim() }),
			});
			testResult = `Test email sent to ${testEmail.trim()}! Check your inbox.`;
			setTimeout(() => (testResult = ''), 8000);
		} catch (e) {
			testError = e instanceof Error ? e.message : 'Failed to send test email';
			setTimeout(() => (testError = ''), 10000);
		} finally {
			testSending = false;
		}
	}

	// -----------------------------------------------------------------------
	// Identity + inbound testing
	// -----------------------------------------------------------------------

	async function checkIdentity() {
		if (!identityEmail.trim()) return;
		checkingIdentity = true;
		identityResult = null;
		try {
			identityResult = await apiJson('/settings/email/check-identity', {
				method: 'POST',
				body: JSON.stringify({ email: identityEmail.trim() }),
			});
		} catch (e) {
			identityResult = { resolved: false, message: e instanceof Error ? e.message : 'Check failed' };
		} finally {
			checkingIdentity = false;
		}
	}

	async function simulateInbound() {
		if (!simFromAddress.trim()) return;
		simulating = true;
		simResult = null;
		try {
			simResult = await apiJson('/settings/email/simulate-inbound', {
				method: 'POST',
				body: JSON.stringify({
					from_address: simFromAddress.trim(),
					subject: simSubject.trim() || 'Test inbound email',
					body: 'This is a simulated inbound email for testing the pipeline.',
				}),
			});
		} catch (e) {
			simResult = { success: false, error: e instanceof Error ? e.message : 'Simulation failed' };
		} finally {
			simulating = false;
		}
	}

	async function loadEmailUsers() {
		try {
			const res = await apiJson<{ users: typeof emailUsers }>('/settings/email/users');
			emailUsers = res.users;
		} catch { /* ignore */ }
	}

	// -----------------------------------------------------------------------
	// Signature image upload
	// -----------------------------------------------------------------------

	async function uploadSignatureImage(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		uploadingImage = true;
		imageUploadError = '';
		try {
			const formData = new FormData();
			formData.append('file', file);
			const res = await fetch('/api/settings/email/signature-image', {
				method: 'POST',
				body: formData,
				headers: {
					'Authorization': `Bearer ${document.cookie.replace(/(?:(?:^|.*;\s*)auth_token\s*=\s*([^;]*).*$)|^.*$/, '$1')}`,
				},
			});
			const data = await res.json();
			if (data.success) {
				form.signature_image_url = data.url;
			} else {
				imageUploadError = data.error || 'Upload failed';
			}
		} catch (e) {
			imageUploadError = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			uploadingImage = false;
			input.value = '';
		}
	}

	async function removeSignatureImage() {
		try {
			await apiJson('/settings/email/signature-image', { method: 'DELETE' });
			form.signature_image_url = '';
		} catch (e) {
			imageUploadError = e instanceof Error ? e.message : 'Failed to remove image';
		}
	}

	// -----------------------------------------------------------------------
	// Tunnel management
	// -----------------------------------------------------------------------

	async function loadTunnelStatus() {
		if (!devMode) return;
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/settings/email/tunnel/status');
		} catch {
			// Tunnel endpoints not available
		}
	}

	async function startTunnel() {
		tunnelLoading = true;
		tunnelStatus = { ...tunnelStatus, error: null };
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/settings/email/tunnel/start', { method: 'POST' });
		} catch (e) {
			tunnelStatus = { ...tunnelStatus, error: e instanceof Error ? e.message : 'Failed to start tunnel' };
		} finally {
			tunnelLoading = false;
		}
	}

	async function stopTunnel() {
		tunnelLoading = true;
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/settings/email/tunnel/stop', { method: 'POST' });
		} catch (e) {
			tunnelStatus = { ...tunnelStatus, error: e instanceof Error ? e.message : 'Failed to stop tunnel' };
		} finally {
			tunnelLoading = false;
		}
	}

	function copyTunnelUrl() {
		if (tunnelStatus.url) {
			navigator.clipboard.writeText(tunnelStatus.url);
			tunnelUrlCopied = true;
			setTimeout(() => (tunnelUrlCopied = false), 2000);
		}
	}

	function copyTunnelWebhookUrl() {
		if (tunnelStatus.url) {
			navigator.clipboard.writeText(`${tunnelStatus.url}/api/email/inbound/${form.provider}`);
			tunnelWebhookCopied = true;
			setTimeout(() => (tunnelWebhookCopied = false), 2000);
		}
	}

	function copyWebhookUrl() {
		const url = `${window.location.origin}/api/email/inbound/${form.provider}`;
		navigator.clipboard.writeText(url);
		webhookCopied = true;
		setTimeout(() => (webhookCopied = false), 2000);
	}
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 px-6 pt-6 pb-4">
		<div class="mb-4 flex items-start justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Email Settings</h1>
				<p class="text-sm text-text-secondary">
					Configure the email channel, provider, identity, and behaviour
				</p>
			</div>
			{#if !isConfigured}
				<button
					type="button"
					onclick={() => (showWizard = true)}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<Sparkles size={14} />
					Setup Wizard
				</button>
			{/if}
		</div>

		<!-- Tab bar -->
		<div class="flex border-b border-border">
			{#each tabs as tab}
				<button
					class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors {activeTab === tab.id ? 'border-b-2 border-accent text-accent' : 'text-text-secondary hover:text-text-primary'}"
					onclick={() => activeTab = tab.id}
				>
					<tab.icon size={14} />
					{tab.label}
				</button>
			{/each}
		</div>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="shrink-0 mx-6 mb-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Success banner -->
	{#if successMsg}
		<div class="shrink-0 mx-6 mb-2 rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success">
			{successMsg}
		</div>
	{/if}

	<!-- Tab content -->
	{#if loading}
		<div class="flex flex-1 items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="flex-1 overflow-y-auto px-6 py-6">
			<div class="flex flex-col gap-6">

				<!-- =========================================================== -->
				<!-- GENERAL TAB                                                  -->
				<!-- =========================================================== -->
				{#if activeTab === 'general'}
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Mail size={16} class="text-ember" />
							Email Channel
						</h2>

						<div class="flex flex-col gap-4">
							<!-- Enable / disable toggle -->
							<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
								<div>
									<span class="block text-xs font-medium text-text-primary">Enable Email Channel</span>
									<span class="block text-[11px] text-text-secondary">
										When enabled, the agent can send and receive emails
									</span>
								</div>
								<button
									type="button"
									role="switch"
									aria-checked={form.enabled}
									onclick={() => (form.enabled = !form.enabled)}
									class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
										{form.enabled ? 'bg-accent' : 'bg-border'}"
								>
									<span
										class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform
											{form.enabled ? 'translate-x-5' : 'translate-x-0'}"
									/>
								</button>
							</div>

							<!-- Status overview -->
							{#if status}
								{#if status.configured}
									<div class="flex items-center gap-3 rounded-lg border border-success/30 bg-success/5 px-4 py-3">
										<CheckCircle size={16} class="shrink-0 text-success" />
										<div class="flex-1">
											<span class="block text-xs font-medium text-text-primary">
												Connected to <span class="capitalize">{status.provider}</span>
											</span>
											<span class="block text-[11px] text-text-secondary">
												Sending from {status.from_address}
											</span>
										</div>
										<button
											type="button"
											onclick={() => (activeTab = 'providers')}
											class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
										>
											<Settings size={10} />
											Manage
										</button>
									</div>
								{:else}
									<div class="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3">
										<AlertCircle size={16} class="shrink-0 text-warning" />
										<div class="flex-1">
											<span class="block text-xs font-medium text-text-primary">Not configured</span>
											<span class="block text-[11px] text-text-secondary">
												Set up an email provider to start sending and receiving emails.
											</span>
										</div>
										<button
											type="button"
											onclick={() => (activeTab = 'providers')}
											class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
										>
											<Package size={12} />
											Configure Provider
										</button>
									</div>
								{/if}
							{/if}
						</div>
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- PROVIDERS TAB                                                -->
				<!-- =========================================================== -->
				{#if activeTab === 'providers'}
					<section class="flex flex-col gap-4">
						<div>
							<h2 class="text-sm font-semibold text-text-primary">Email Providers</h2>
							<p class="mt-1 text-xs text-text-secondary">
								Choose and configure your email provider. Only one provider can be active at a time.
							</p>
						</div>

						<!-- Provider Cards -->
						<div class="grid grid-cols-2 gap-4">
							{#each PROVIDERS as provider}
								{@const isCurrent = form.provider === provider.id && isConfigured}
								{@const isBeingConfigured = configuringProvider === provider.id}
								<div
									class="relative flex flex-col rounded-lg border-2 transition-colors {isCurrent ? 'border-success/50 bg-success/5' : isBeingConfigured ? 'border-accent/50 bg-accent/5' : 'border-border bg-surface hover:border-border-hover'}"
								>
									<!-- Active badge -->
									{#if isCurrent}
										<div class="absolute -top-2.5 left-3 flex items-center gap-1 rounded-full bg-success px-2 py-0.5 text-[10px] font-semibold text-white">
											<CheckCircle size={10} />
											Active
										</div>
									{/if}

									<div class="flex flex-col gap-3 p-5 pt-4">
										<div class="flex items-start justify-between">
											<div class="flex items-center gap-2.5">
												<div class="flex h-9 w-9 items-center justify-center rounded-lg {isCurrent ? 'bg-success/10' : 'bg-surface-secondary'}">
													<provider.icon size={18} class={isCurrent ? 'text-success' : 'text-text-secondary'} />
												</div>
												<div>
													<span class="block text-sm font-semibold text-text-primary">{provider.name}</span>
												</div>
											</div>
										</div>

										<p class="text-xs leading-relaxed text-text-secondary">{provider.description}</p>

										<!-- Feature tags -->
										<div class="flex flex-wrap gap-1.5">
											{#each provider.features as feature}
												<span class="rounded-full border border-border/50 bg-surface-secondary/50 px-2 py-0.5 text-[10px] text-text-secondary">
													{feature}
												</span>
											{/each}
										</div>

										<!-- Actions -->
										<div class="mt-1 flex items-center gap-2">
											{#if isCurrent && !isBeingConfigured}
												<button
													type="button"
													onclick={() => (configuringProvider = provider.id)}
													class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
												>
													<Settings size={11} />
													Reconfigure
												</button>
												<button
													type="button"
													onclick={() => (showDisconnectModal = true)}
													class="inline-flex items-center gap-1 rounded-md border border-danger/30 px-2.5 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/10"
												>
													<Unplug size={11} />
													Disconnect
												</button>
											{:else if !isCurrent && !isBeingConfigured}
												<button
													type="button"
													onclick={() => selectProvider(provider.id)}
													class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
												>
													<Settings size={11} />
													Configure
												</button>
											{/if}
										</div>
									</div>

									<!-- Inline configuration form -->
									{#if isBeingConfigured}
										<div class="border-t border-border/50 p-5">
											<div class="flex flex-col gap-3">
												<label class="flex flex-col gap-1">
													<span class="text-xs font-medium text-text-secondary">API Key</span>
													<input
														type="password"
														bind:value={form.provider_api_key}
														placeholder={provider.id === 'resend' ? 're_...' : 'AKIA...'}
														class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
													/>
													<span class="text-xs text-text-secondary">
														{provider.id === 'resend' ? 'Your Resend API key' : 'AWS access key for SES'}
													</span>
												</label>

												{#if provider.id === 'ses'}
													<label class="flex flex-col gap-1">
														<span class="text-xs font-medium text-text-secondary">AWS Region</span>
														<input
															type="text"
															bind:value={form.provider_region}
															placeholder="us-east-1"
															class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
														/>
													</label>
												{/if}

												<!-- Validate + Save row -->
												<div class="flex items-center gap-2">
													<button
														type="button"
														onclick={validateConnection}
														disabled={validating || !form.provider_api_key}
														class="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors {validateResult?.success ? 'bg-success/10 text-success border border-success/30' : validateResult && !validateResult.success ? 'bg-danger/10 text-danger border border-danger/30' : 'border border-border text-text-secondary hover:bg-surface-hover hover:text-text-primary'} disabled:opacity-50"
													>
														{#if validating}
															<Loader2 size={11} class="animate-spin" />
															Testing…
														{:else if validateResult?.success}
															<CheckCircle size={11} />
															Connected
														{:else if validateResult && !validateResult.success}
															<AlertCircle size={11} />
															Failed
														{:else}
															Test Connection
														{/if}
													</button>

													<button
														type="button"
														onclick={cancelProviderConfig}
														class="rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
													>
														Cancel
													</button>
												</div>

												{#if validateResult && !validateResult.success}
													<span class="text-xs text-danger">{validateResult.error}</span>
												{:else if validateResult?.success && validateResult.details?.domains?.length}
													<span class="text-xs text-success">Verified domains: {validateResult.details.domains.join(', ')}</span>
												{/if}
											</div>
										</div>
									{/if}
								</div>
							{/each}
						</div>
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- IDENTITY TAB                                                 -->
				<!-- =========================================================== -->
				{#if activeTab === 'identity'}
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<CircleUser size={16} class="text-ember" />
							Sender Identity
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Configure how the agent identifies itself in outgoing emails.
						</p>

						<div class="flex flex-col gap-4">
							<div class="grid grid-cols-2 gap-4">
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">From Address</span>
									<input
										type="email"
										bind:value={form.from_address}
										placeholder="ember@flydesk.ai"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
									/>
									<span class="text-xs text-text-secondary">The email address used as the sender</span>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Display Name</span>
									<input
										type="text"
										bind:value={form.from_display_name}
										placeholder="Ember"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
									/>
									<span class="text-xs text-text-secondary">Shown as the sender name in email clients</span>
								</label>
							</div>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Reply-To Address</span>
								<input
									type="email"
									bind:value={form.reply_to}
									placeholder="support@yourcompany.com"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
								<span class="text-xs text-text-secondary">
									Optional. If set, replies will be directed to this address instead of the from address.
								</span>
							</label>

							<!-- Domain badge -->
							{#if form.from_address.includes('@')}
								<div class="flex items-center gap-2 rounded-md border border-border/50 bg-surface-secondary/30 px-3 py-2">
									<Globe size={14} class="shrink-0 text-text-secondary" />
									<span class="text-xs text-text-secondary">
										Sending domain: <span class="font-medium text-text-primary">{form.from_address.split('@')[1]}</span>
									</span>
								</div>
							{/if}
						</div>
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- SIGNATURE TAB                                                -->
				<!-- =========================================================== -->
				{#if activeTab === 'signature'}
					<!-- Signature Image / Logo -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<ImagePlus size={16} class="text-ember" />
							Signature Logo
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Upload a logo or image to display in your email signature. Stored as base64 for maximum portability.
						</p>

						<div class="flex items-start gap-5">
							<div class="shrink-0">
								{#if form.signature_image_url}
									<div class="relative group">
										<img
											src={form.signature_image_url}
											alt="Signature logo"
											class="h-16 w-16 rounded-lg border border-border object-contain bg-white p-1"
										/>
										<button
											type="button"
											onclick={removeSignatureImage}
											class="absolute -top-2 -right-2 hidden group-hover:flex h-5 w-5 items-center justify-center rounded-full bg-danger text-white shadow transition-transform hover:scale-110"
											title="Remove image"
										>
											<Trash2 size={10} />
										</button>
									</div>
								{:else}
									<div class="flex h-16 w-16 items-center justify-center rounded-lg border-2 border-dashed border-border bg-surface-secondary/30">
										<ImagePlus size={20} class="text-text-secondary/50" />
									</div>
								{/if}
							</div>

							<div class="flex flex-col gap-2">
								<label
									class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary {uploadingImage ? 'opacity-50 pointer-events-none' : ''}"
								>
									{#if uploadingImage}
										<Loader2 size={12} class="animate-spin" />
										Uploading…
									{:else}
										<Upload size={12} />
										{form.signature_image_url ? 'Replace Image' : 'Upload Image'}
									{/if}
									<input
										type="file"
										accept="image/png,image/jpeg,image/gif,image/webp"
										class="hidden"
										onchange={uploadSignatureImage}
										disabled={uploadingImage}
									/>
								</label>
								<span class="text-[10px] text-text-secondary">
									PNG, JPEG, GIF, or WebP. Max 2 MB.
								</span>
								{#if imageUploadError}
									<span class="text-xs text-danger">{imageUploadError}</span>
								{/if}
							</div>
						</div>
					</section>

					<!-- Signature HTML -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<div class="mb-4 flex items-center justify-between">
							<h2 class="text-sm font-semibold text-text-primary">Email Signature</h2>

							<div class="flex items-center gap-2">
								<button
									type="button"
									onclick={resetSignatureToDefault}
									disabled={resettingSignature}
									class="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-50"
								>
									{#if resettingSignature}
										<Loader2 size={12} class="animate-spin" />
									{:else}
										<RotateCcw size={12} />
									{/if}
									Reset to Default
								</button>

								<button
									type="button"
									onclick={() => signatureEditing = !signatureEditing}
									class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors {signatureEditing ? 'bg-accent text-white border-accent' : 'border-border text-text-secondary hover:bg-surface-hover hover:text-text-primary'}"
								>
									{#if signatureEditing}
										<Eye size={12} />
										Preview
									{:else}
										<Pencil size={12} />
										Edit HTML
									{/if}
								</button>
							</div>
						</div>

						{#if form.signature_html}
							<div class="overflow-hidden rounded-md border border-border/50 bg-white">
								{#key form.signature_html}
									<iframe
										srcdoc={signaturePreviewHtml}
										title="Signature preview"
										class="block w-full border-0"
										style="min-height: 60px;"
										sandbox="allow-same-origin"
										onload={resizePreviewIframe}
									></iframe>
								{/key}
							</div>

							{#if signatureEditing}
								<div class="mt-4 flex flex-col gap-1">
									<label class="text-xs font-medium text-text-secondary">HTML Source</label>
									<CodeEditor
										value={form.signature_html}
										language="html"
										placeholder={'<table cellpadding="0" cellspacing="0">\n  <tr>\n    <td>Your signature here</td>\n  </tr>\n</table>'}
										minHeight="220px"
										onchange={(v) => form.signature_html = v}
									/>
									<span class="text-xs text-text-secondary">
										Email-safe HTML (tables, inline styles). Changes update the preview above in real time.
									</span>
								</div>
							{/if}
						{:else}
							<div class="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border/70 py-8 text-text-secondary">
								<Signature size={20} class="opacity-50" />
								<p class="text-sm">No signature configured yet</p>
								<button
									type="button"
									onclick={resetSignatureToDefault}
									disabled={resettingSignature}
									class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90"
								>
									{#if resettingSignature}
										<Loader2 size={12} class="animate-spin" />
									{:else}
										<RotateCcw size={12} />
									{/if}
									Generate Default Signature
								</button>
							</div>
						{/if}
					</section>

					<!-- Plain Text Fallback -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 text-sm font-semibold text-text-primary">Plain Text Fallback</h2>
						<textarea
							bind:value={form.signature_text}
							placeholder="Best regards,&#10;Ember - AI Assistant"
							rows={3}
							class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						></textarea>
						<span class="text-xs text-text-secondary">
							Fallback for plain text emails. If empty, the HTML signature will be stripped of tags.
						</span>
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- BEHAVIOUR TAB                                                -->
				<!-- =========================================================== -->
				{#if activeTab === 'behaviour'}
					<!-- Auto-reply & Timing -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Clock size={16} class="text-ember" />
							Auto-Reply
						</h2>

						<div class="flex flex-col gap-4">
							<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
								<div>
									<span class="block text-xs font-medium text-text-primary">Auto-Reply</span>
									<span class="block text-[11px] text-text-secondary">
										Automatically respond to incoming emails without approval
									</span>
								</div>
								<button
									type="button"
									role="switch"
									aria-checked={form.auto_reply}
									onclick={() => (form.auto_reply = !form.auto_reply)}
									class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
										{form.auto_reply ? 'bg-accent' : 'bg-border'}"
								>
									<span
										class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform
											{form.auto_reply ? 'translate-x-5' : 'translate-x-0'}"
									/>
								</button>
							</div>

							{#if form.auto_reply}
								<label class="flex flex-col gap-1">
									<div class="flex items-center justify-between">
										<span class="text-xs font-medium text-text-secondary">Reply Delay</span>
										<span class="text-xs font-medium text-text-primary">{delayLabel}</span>
									</div>
									<input
										type="range"
										min={0}
										max={300}
										step={5}
										bind:value={form.auto_reply_delay_seconds}
										class="w-full accent-accent"
									/>
									<span class="text-xs text-text-secondary">
										Wait before sending an auto-reply. 0 = immediate.
									</span>
								</label>
							{/if}

							<label class="flex flex-col gap-1">
								<div class="flex items-center justify-between">
									<span class="text-xs font-medium text-text-secondary">Max Email Length</span>
									<span class="text-xs font-medium text-text-primary">{form.max_email_length} chars</span>
								</div>
								<input
									type="range"
									min={200}
									max={10000}
									step={100}
									bind:value={form.max_email_length}
									class="w-full accent-accent"
								/>
							</label>
						</div>
					</section>

					<!-- Greeting & Sign-off -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 text-sm font-semibold text-text-primary">Greeting &amp; Sign-Off</h2>

						<div class="flex flex-col gap-4">
							<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
								<div>
									<span class="block text-xs font-medium text-text-primary">Include Greeting</span>
									<span class="block text-[11px] text-text-secondary">Start emails with "Hi [Name],"</span>
								</div>
								<button
									type="button"
									role="switch"
									aria-checked={form.include_greeting}
									onclick={() => (form.include_greeting = !form.include_greeting)}
									class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
										{form.include_greeting ? 'bg-accent' : 'bg-border'}"
								>
									<span class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform {form.include_greeting ? 'translate-x-5' : 'translate-x-0'}" />
								</button>
							</div>

							<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
								<div>
									<span class="block text-xs font-medium text-text-primary">Include Sign-Off</span>
									<span class="block text-[11px] text-text-secondary">End emails with "Best regards, Ember"</span>
								</div>
								<button
									type="button"
									role="switch"
									aria-checked={form.include_sign_off}
									onclick={() => (form.include_sign_off = !form.include_sign_off)}
									class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
										{form.include_sign_off ? 'bg-accent' : 'bg-border'}"
								>
									<span class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform {form.include_sign_off ? 'translate-x-5' : 'translate-x-0'}" />
								</button>
							</div>
						</div>
					</section>

					<!-- Persona / Tone -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<MessageSquare size={16} class="text-ember" />
							Tone &amp; Personality
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Customise how the agent writes emails. If left empty, these inherit from global Agent settings.
						</p>

						<div class="flex flex-col gap-4">
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Tone</span>
								<input
									type="text"
									bind:value={form.email_tone}
									placeholder="e.g. professional, warm, concise"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Personality</span>
								<textarea
									bind:value={form.email_personality}
									placeholder="Describe the email persona..."
									rows={3}
									class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								></textarea>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Custom Instructions</span>
								<textarea
									bind:value={form.email_instructions}
									placeholder="Additional instructions for email composition..."
									rows={4}
									class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								></textarea>
								<span class="text-xs text-text-secondary">
									Free-form instructions appended to the email system prompt.
								</span>
							</label>
						</div>
					</section>

					<!-- CC Behaviour -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Users size={16} class="text-ember" />
							CC Behaviour
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Control how the agent handles emails where it is CC'd.
						</p>

						<div class="flex flex-col gap-4">
							<div class="flex flex-col gap-2">
								<label class="flex items-start gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-secondary/80">
									<input type="radio" name="cc_mode" value="respond_all" bind:group={form.cc_mode} class="mt-0.5 accent-accent" />
									<div>
										<span class="block text-xs font-medium text-text-primary">Reply All</span>
										<span class="block text-[11px] text-text-secondary">Respond to the entire thread</span>
									</div>
								</label>

								<label class="flex items-start gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-secondary/80">
									<input type="radio" name="cc_mode" value="respond_sender" bind:group={form.cc_mode} class="mt-0.5 accent-accent" />
									<div>
										<span class="block text-xs font-medium text-text-primary">Reply to Sender Only</span>
										<span class="block text-[11px] text-text-secondary">Respond only to the person who sent the email</span>
									</div>
								</label>

								<label class="flex items-start gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-secondary/80">
									<input type="radio" name="cc_mode" value="silent" bind:group={form.cc_mode} class="mt-0.5 accent-accent" />
									<div>
										<span class="block text-xs font-medium text-text-primary">Silent</span>
										<span class="block text-[11px] text-text-secondary">Do not respond when CC'd</span>
									</div>
								</label>
							</div>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">CC Instructions</span>
								<textarea
									bind:value={form.cc_instructions}
									placeholder="Additional instructions for handling CC'd emails..."
									rows={3}
									class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								></textarea>
							</label>
						</div>
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- OUTBOUND TAB                                                 -->
				<!-- =========================================================== -->
				{#if activeTab === 'outbound'}
					<!-- Send Test Email -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Send size={16} class="text-ember" />
							Send Test Email
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Verify your email configuration by sending a test message. Save your settings first.
						</p>

						{#if !isConfigured}
							<div class="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3">
								<AlertCircle size={16} class="shrink-0 text-warning" />
								<span class="text-xs text-text-secondary">
									Configure an email provider first before sending test emails.
								</span>
								<button
									type="button"
									onclick={() => (activeTab = 'providers')}
									class="ml-auto inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
								>
									<Package size={11} />
									Go to Providers
								</button>
							</div>
						{:else}
							<div class="flex flex-col gap-3">
								<div class="flex gap-2">
									<input
										type="email"
										bind:value={testEmail}
										placeholder="recipient@example.com"
										onkeydown={(e) => {
											if (e.key === 'Enter') {
												e.preventDefault();
												sendTestEmail();
											}
										}}
										class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
									/>
									<button
										type="button"
										onclick={sendTestEmail}
										disabled={testSending || !testEmail.trim()}
										class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
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
									<div class="rounded-lg border border-success/30 bg-success/5 px-3 py-2 text-xs text-success">
										{testResult}
									</div>
								{/if}

								{#if testError}
									<div class="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
										{testError}
									</div>
								{/if}
							</div>
						{/if}
					</section>

					<!-- DNS Recommendations -->
					<section class="rounded-lg border border-border bg-surface">
						<button
							type="button"
							onclick={() => (dnsExpanded = !dnsExpanded)}
							class="flex w-full items-center justify-between px-5 py-4"
						>
							<h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
								<ShieldCheck size={16} class="text-ember" />
								DNS Recommendations
							</h2>
							{#if dnsExpanded}
								<ChevronDown size={16} class="text-text-secondary" />
							{:else}
								<ChevronRight size={16} class="text-text-secondary" />
							{/if}
						</button>

						{#if dnsExpanded}
							<div class="border-t border-border px-5 pb-5 pt-3">
								<p class="mb-4 text-xs text-text-secondary">
									Configure these DNS records for your sending domain to improve deliverability and prevent emails from landing in spam.
								</p>

								<div class="flex flex-col gap-3">
									<div class="rounded-md border border-border/50 bg-surface-secondary/30 p-3">
										<div class="mb-1.5 flex items-center gap-2">
											<span class="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-bold text-accent">SPF</span>
											<span class="text-xs font-medium text-text-primary">Sender Policy Framework</span>
										</div>
										<p class="mb-1.5 text-[11px] text-text-secondary">
											Add an SPF record to your domain's DNS. Include your email provider's SPF directive.
										</p>
										<code class="block rounded bg-surface px-2 py-1 text-[11px] text-text-primary">
											v=spf1 include:<span class="text-accent">&lt;your-provider-spf&gt;</span> ~all
										</code>
									</div>

									<div class="rounded-md border border-border/50 bg-surface-secondary/30 p-3">
										<div class="mb-1.5 flex items-center gap-2">
											<span class="rounded bg-success/10 px-1.5 py-0.5 text-[10px] font-bold text-success">DKIM</span>
											<span class="text-xs font-medium text-text-primary">DomainKeys Identified Mail</span>
										</div>
										<p class="text-[11px] text-text-secondary">
											Most email providers handle DKIM signing automatically once you verify your domain.
											Check your provider's documentation for specific DKIM setup instructions.
										</p>
									</div>

									<div class="rounded-md border border-border/50 bg-surface-secondary/30 p-3">
										<div class="mb-1.5 flex items-center gap-2">
											<span class="rounded bg-warning/10 px-1.5 py-0.5 text-[10px] font-bold text-warning">DMARC</span>
											<span class="text-xs font-medium text-text-primary">Domain-based Message Authentication</span>
										</div>
										<p class="mb-1.5 text-[11px] text-text-secondary">
											Add a DMARC record to monitor and enforce email authentication for your domain.
										</p>
										<code class="block rounded bg-surface px-2 py-1 text-[11px] text-text-primary">
											v=DMARC1; p=none; rua=mailto:dmarc@{form.from_address.split('@')[1] || 'yourdomain.com'}
										</code>
									</div>
								</div>
							</div>
						{/if}
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- INBOUND TAB                                                  -->
				<!-- =========================================================== -->
				{#if activeTab === 'inbound'}
					<!-- Webhook Setup -->
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Globe size={16} class="text-ember" />
							Inbound Webhook
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Configure your email provider to forward webhooks to this endpoint.
						</p>

						<div class="mb-4">
							<label class="mb-1 block text-xs font-medium text-text-secondary">Webhook Endpoint</label>
							<div class="flex items-center gap-2">
								<code class="flex-1 rounded-md border border-border bg-surface-secondary/50 px-3 py-2 text-xs text-text-primary">
									{window.location.origin}/api/email/inbound/{form.provider}
								</code>
								<button
									type="button"
									onclick={copyWebhookUrl}
									class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-2 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
								>
									{#if webhookCopied}
										<CheckCircle size={12} class="text-success" />
										Copied
									{:else}
										<Copy size={12} />
										Copy
									{/if}
								</button>
							</div>
						</div>

						<!-- Setup Steps -->
						<div class="rounded-md border border-border/50 bg-surface-secondary/20 p-3">
							<h3 class="mb-2 text-xs font-medium text-text-primary">Setup Instructions</h3>
							{#if form.provider === 'resend'}
								<ol class="flex flex-col gap-1.5 text-[11px] text-text-secondary">
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">1.</span>
										Go to your provider's webhook settings dashboard.
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
										Save the webhook.
									</li>
								</ol>
							{:else}
								<ol class="flex flex-col gap-1.5 text-[11px] text-text-secondary">
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">1.</span>
										In the SES Console, go to <strong>Email Receiving &gt; Rule Sets</strong>.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">2.</span>
										Create a rule sending inbound emails to an <strong>SNS Topic</strong>.
									</li>
									<li class="flex gap-2">
										<span class="shrink-0 font-bold text-accent">3.</span>
										Add an <strong>HTTPS subscription</strong> with the endpoint URL above.
									</li>
								</ol>
							{/if}
						</div>
					</section>

					<!-- Dev Tunnel -->
					{#if devMode}
						<section class="rounded-lg border border-accent/30 bg-accent/5 p-5">
							<h2 class="mb-2 flex items-center gap-2 text-sm font-semibold text-text-primary">
								<Radio size={16} class="text-accent" />
								Dev Tunnel (ngrok)
							</h2>

							{#if tunnelStatus.available}
								<p class="mb-3 text-xs text-text-secondary">
									Expose your local server to the internet for real-time webhook delivery.
								</p>

								<div class="flex flex-col gap-3">
									<div class="flex items-center gap-3">
										{#if tunnelStatus.active}
											<button
												type="button"
												onclick={stopTunnel}
												disabled={tunnelLoading}
												class="inline-flex items-center gap-1.5 rounded-md border border-danger/30 bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/20 disabled:opacity-50"
											>
												{#if tunnelLoading}
													<Loader2 size={12} class="animate-spin" />
												{:else}
													<PowerOff size={12} />
												{/if}
												Stop Tunnel
											</button>
											<span class="inline-flex items-center gap-1.5 text-xs text-success">
												<span class="inline-block h-2 w-2 rounded-full bg-success animate-pulse"></span>
												Active
											</span>
										{:else}
											<button
												type="button"
												onclick={startTunnel}
												disabled={tunnelLoading}
												class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
											>
												{#if tunnelLoading}
													<Loader2 size={12} class="animate-spin" />
													Starting…
												{:else}
													<Power size={12} />
													Start Tunnel
												{/if}
											</button>
											<span class="text-xs text-text-secondary">Not running</span>
										{/if}
									</div>

									{#if tunnelStatus.error}
										<div class="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
											{tunnelStatus.error}
										</div>
									{/if}

									{#if tunnelStatus.active && tunnelStatus.url}
										<div class="flex flex-col gap-2">
											<label class="text-[11px] font-medium text-text-secondary">Tunnel URL</label>
											<div class="flex items-center gap-2">
												<code class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary">
													{tunnelStatus.url}
												</code>
												<button
													type="button"
													onclick={copyTunnelUrl}
													class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
												>
													{#if tunnelUrlCopied}<CheckCircle size={10} class="text-success" />{:else}<Copy size={10} />{/if}
												</button>
											</div>
										</div>

										<div class="flex flex-col gap-2">
											<label class="text-[11px] font-medium text-text-secondary">Webhook URL (via tunnel)</label>
											<div class="flex items-center gap-2">
												<code class="flex-1 rounded-md border border-success/30 bg-success/5 px-3 py-1.5 text-xs text-success font-medium">
													{tunnelStatus.url}/api/email/inbound/{form.provider}
												</code>
												<button
													type="button"
													onclick={copyTunnelWebhookUrl}
													class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
												>
													{#if tunnelWebhookCopied}<CheckCircle size={10} class="text-success" />{:else}<Copy size={10} />{/if}
												</button>
											</div>
										</div>
									{/if}
								</div>
							{:else}
								<p class="text-[11px] text-text-secondary">
									Install <a href="https://ngrok.com/download" target="_blank" rel="noopener noreferrer" class="font-medium text-accent underline">ngrok</a> and
									<code class="rounded bg-surface px-1 text-[10px]">pyngrok</code> to enable tunnel support.
								</p>
								<code class="mt-2 block rounded bg-surface px-2 py-1 text-[10px] text-text-secondary">
									pip install pyngrok && ngrok config add-authtoken YOUR_TOKEN
								</code>
							{/if}
						</section>
					{/if}

					<!-- Pipeline Testing -->
					<section class="rounded-lg border border-amber-200/60 bg-amber-50/30 p-5">
						<h2 class="mb-1 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Zap size={16} class="text-amber-500" />
							Inbound Pipeline Testing
						</h2>
						<p class="mb-4 text-xs text-text-secondary">
							Simulate receiving an email to test identity resolution, threading, and auto-reply.
						</p>

						<!-- Email Users -->
						<div class="mb-4">
							<h3 class="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-secondary">
								<UserCheck size={12} />
								Email-Enabled Users ({emailUsers.length})
							</h3>
							{#if emailUsers.length > 0}
								<div class="flex flex-wrap gap-1.5">
									{#each emailUsers as u}
										<button
											type="button"
											onclick={() => { simFromAddress = u.email; identityEmail = u.email; }}
											class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs transition-colors {u.is_active ? 'border-success/30 bg-success/5 text-success hover:bg-success/10' : 'border-border bg-surface text-text-secondary'}"
										>
											<span class="font-medium">{u.display_name || u.username}</span>
											<span class="opacity-60">{u.email}</span>
										</button>
									{/each}
								</div>
							{:else}
								<p class="text-xs text-text-secondary italic">No users with email addresses found.</p>
							{/if}
						</div>

						<!-- Identity Check -->
						<div class="mb-4 rounded-md border border-border/50 bg-surface p-3">
							<h3 class="mb-2 text-xs font-medium text-text-secondary">Check Identity Resolution</h3>
							<div class="flex gap-2">
								<input
									type="email"
									bind:value={identityEmail}
									placeholder="sender@example.com"
									onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); checkIdentity(); } }}
									class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
								<button
									type="button"
									onclick={checkIdentity}
									disabled={checkingIdentity || !identityEmail.trim()}
									class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
								>
									{#if checkingIdentity}
										<Loader2 size={12} class="animate-spin" />
									{:else}
										<UserCheck size={12} />
									{/if}
									Check
								</button>
							</div>
							{#if identityResult}
								<div class="mt-2 rounded-md px-3 py-1.5 text-xs {identityResult.resolved ? 'border border-success/30 bg-success/5 text-success' : 'border border-danger/30 bg-danger/5 text-danger'}">
									{#if identityResult.resolved}
										<CheckCircle size={10} class="mr-1 inline" />
										<strong>{identityResult.display_name}</strong> ({identityResult.email})
									{:else}
										<AlertCircle size={10} class="mr-1 inline" />
										{identityResult.message}
									{/if}
								</div>
							{/if}
						</div>

						<!-- Simulate Inbound -->
						<div class="rounded-md border border-border/50 bg-surface p-3">
							<h3 class="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-secondary">
								<Inbox size={12} />
								Simulate Inbound Email
							</h3>
							<div class="flex flex-col gap-2">
								<div class="grid grid-cols-2 gap-2">
									<input
										type="email"
										bind:value={simFromAddress}
										placeholder="sender@example.com"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
									/>
									<input
										type="text"
										bind:value={simSubject}
										placeholder="Email subject"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
									/>
								</div>
								<button
									type="button"
									onclick={simulateInbound}
									disabled={simulating || !simFromAddress.trim()}
									class="inline-flex items-center gap-1.5 self-start rounded-md bg-amber-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-amber-600 disabled:opacity-50"
								>
									{#if simulating}
										<Loader2 size={14} class="animate-spin" />
										Running Pipeline…
									{:else}
										<Zap size={14} />
										Simulate Inbound
									{/if}
								</button>
							</div>

							{#if simResult}
								<div class="mt-3 rounded-md border {simResult.success ? 'border-success/30 bg-success/5' : 'border-danger/30 bg-danger/5'} p-3 text-xs">
									{#if simResult.success}
										<div class="mb-2 font-medium text-success"><CheckCircle size={12} class="mr-1 inline" /> Pipeline completed</div>
										<div class="space-y-1 text-text-secondary">
											<div><strong>Identity:</strong> {simResult.identity?.display_name} ({simResult.identity?.email})</div>
											<div><strong>Conversation:</strong> {simResult.thread?.conversation_id} {simResult.thread?.is_new ? '(new)' : '(existing)'}</div>
											<div><strong>Auto-reply:</strong> {simResult.auto_reply_enabled ? 'enabled' : 'disabled'}</div>
											{#if simResult.reply_sent}
												<div class="text-success"><strong>Reply sent!</strong> ID: {simResult.reply_message_id}</div>
											{:else if simResult.reply_note}
												<div><strong>Reply:</strong> {simResult.reply_note}</div>
											{:else if simResult.reply_error}
												<div class="text-danger"><strong>Reply failed:</strong> {simResult.reply_error}</div>
											{/if}
										</div>
									{:else}
										<div class="text-danger">
											<AlertCircle size={12} class="mr-1 inline" />
											{simResult.error || 'Simulation failed'}
										</div>
									{/if}
								</div>
							{/if}
						</div>
					</section>
				{/if}

			</div>
		</div>
	{/if}

	<!-- Sticky footer with Save / Reset buttons -->
	{#if !loading}
		<div class="shrink-0 border-t border-border bg-surface px-6 py-3">
			<div class="flex items-center justify-end gap-2">
				<button
					type="button"
					onclick={resetToDefaults}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<RotateCcw size={14} />
					Reset to Defaults
				</button>
				<button
					type="button"
					onclick={saveSettings}
					disabled={saving}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Save size={14} />
					{/if}
					Save Changes
				</button>
			</div>
		</div>
	{/if}
</div>

<!-- Disconnect Confirmation Modal -->
{#if showDisconnectModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
		<div class="w-full max-w-sm rounded-lg border border-border bg-surface p-6 shadow-xl">
			<h3 class="mb-2 text-sm font-semibold text-text-primary">Disconnect Email?</h3>
			<p class="mb-5 text-xs text-text-secondary">
				This will clear your provider API key and disable the email channel. You can reconfigure it later.
			</p>
			<div class="flex items-center justify-end gap-2">
				<button
					type="button"
					onclick={() => (showDisconnectModal = false)}
					class="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={disconnectEmail}
					disabled={disconnecting}
					class="inline-flex items-center gap-1.5 rounded-md bg-danger px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-danger/90 disabled:opacity-50"
				>
					{#if disconnecting}
						<Loader2 size={12} class="animate-spin" />
					{:else}
						<Unplug size={12} />
					{/if}
					Disconnect
				</button>
			</div>
		</div>
	</div>
{/if}

<EmailSetupWizard
	open={showWizard}
	{devMode}
	onClose={() => (showWizard = false)}
	onSaved={() => {
		showWizard = false;
		loadSettings();
	}}
/>
