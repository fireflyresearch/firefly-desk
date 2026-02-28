<!--
  EmailSettings.svelte - Admin panel for email channel configuration.

  Allows administrators to configure the email provider, identity, signature,
  persona, behaviour settings, CC handling, and send test emails.

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
		Settings
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

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

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');

	let testEmail = $state('');
	let testSending = $state(false);
	let testResult = $state('');
	let testError = $state('');

	let status = $state<EmailStatus | null>(null);

	// Form state -- matches EmailSettings backend model
	let form = $state<EmailSettingsData>({ ...EMAIL_DEFAULTS });

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let delayLabel = $derived(
		form.auto_reply_delay_seconds < 60
			? `${form.auto_reply_delay_seconds}s`
			: `${Math.floor(form.auto_reply_delay_seconds / 60)}m ${form.auto_reply_delay_seconds % 60}s`
	);

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
			// Refresh status after save
			status = await apiJson<EmailStatus>('/settings/email/status');
			successMsg = 'Email settings saved successfully.';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save email settings';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Reset to defaults
	// -----------------------------------------------------------------------

	function resetToDefaults() {
		form = { ...EMAIL_DEFAULTS };
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
			testResult = `Test email sent to ${testEmail.trim()}`;
			setTimeout(() => (testResult = ''), 6000);
		} catch (e) {
			testError = e instanceof Error ? e.message : 'Failed to send test email';
			setTimeout(() => (testError = ''), 6000);
		} finally {
			testSending = false;
		}
	}
</script>

<div class="flex h-full flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Email Settings</h1>
			<p class="text-sm text-text-secondary">
				Configure the email channel, provider, identity, and behaviour
			</p>
		</div>
		<div class="flex items-center gap-2">
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

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Success banner -->
	{#if successMsg}
		<div class="rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success">
			{successMsg}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="flex flex-col gap-6">
			<!-- ============================================================= -->
			<!-- Status Card                                                    -->
			<!-- ============================================================= -->
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

					<!-- Status indicator -->
					{#if status}
						<div class="flex items-center gap-3 rounded-lg border border-border/50 bg-surface-secondary/30 px-4 py-2.5">
							{#if status.configured}
								<CheckCircle size={16} class="shrink-0 text-success" />
								<span class="text-xs text-text-secondary">
									Provider <span class="font-medium text-text-primary">{status.provider}</span> is configured.
									Sending from <span class="font-medium text-text-primary">{status.from_address}</span>
								</span>
							{:else}
								<AlertCircle size={16} class="shrink-0 text-warning" />
								<span class="text-xs text-text-secondary">
									Email provider is not yet configured. Add your provider credentials below.
								</span>
							{/if}
						</div>
					{/if}
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- Provider Configuration                                         -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
					<Settings size={16} class="text-ember" />
					Provider Configuration
				</h2>

				<div class="flex flex-col gap-4">
					<!-- Provider select -->
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Email Provider</span>
						<select
							bind:value={form.provider}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						>
							<option value="resend">Resend</option>
							<option value="ses">Amazon SES</option>
						</select>
					</label>

					<!-- API Key -->
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">API Key</span>
						<input
							type="password"
							bind:value={form.provider_api_key}
							placeholder={form.provider === 'resend' ? 're_...' : 'AKIA...'}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						/>
						<span class="text-xs text-text-secondary">
							{form.provider === 'resend' ? 'Your Resend API key' : 'AWS access key for SES'}
						</span>
					</label>

					<!-- Region (SES only) -->
					{#if form.provider === 'ses'}
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">AWS Region</span>
							<input
								type="text"
								bind:value={form.provider_region}
								placeholder="us-east-1"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
							/>
							<span class="text-xs text-text-secondary">
								The AWS region where SES is configured (e.g. us-east-1, eu-west-1)
							</span>
						</label>
					{/if}
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- Identity                                                       -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 text-sm font-semibold text-text-primary">Identity</h2>

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
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- Signature                                                      -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 text-sm font-semibold text-text-primary">Signature</h2>

				<div class="flex flex-col gap-4">
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">HTML Signature</span>
						<textarea
							bind:value={form.signature_html}
							placeholder="<p>Best regards,<br>Ember - AI Assistant</p>"
							rows={4}
							class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent font-mono"
						></textarea>
						<span class="text-xs text-text-secondary">
							HTML markup appended to outgoing emails. Supports standard HTML tags.
						</span>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Plain Text Signature</span>
						<textarea
							bind:value={form.signature_text}
							placeholder="Best regards,&#10;Ember - AI Assistant"
							rows={3}
							class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						></textarea>
						<span class="text-xs text-text-secondary">
							Fallback for plain text emails. If empty, the HTML signature will be stripped of tags.
						</span>
					</label>
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- Email Persona                                                  -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
					<MessageSquare size={16} class="text-ember" />
					Email Persona
				</h2>
				<p class="mb-4 text-xs text-text-secondary">
					Customise how the agent writes emails. If left empty, these fields inherit from the global Agent settings.
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
						<span class="text-xs text-text-secondary">
							The desired tone for email responses. Leave empty to use the agent default.
						</span>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Personality</span>
						<textarea
							bind:value={form.email_personality}
							placeholder="Describe the email persona..."
							rows={3}
							class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						></textarea>
						<span class="text-xs text-text-secondary">
							A brief description of the persona used when composing emails. Inherits from Agent if empty.
						</span>
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
							Free-form instructions appended to the email system prompt. Use for special formatting, disclaimers, etc.
						</span>
					</label>
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- Behaviour                                                      -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
					<Clock size={16} class="text-ember" />
					Behaviour
				</h2>

				<div class="flex flex-col gap-4">
					<!-- Auto-reply toggle -->
					<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
						<div>
							<span class="block text-xs font-medium text-text-primary">Auto-Reply</span>
							<span class="block text-[11px] text-text-secondary">
								Automatically respond to incoming emails without agent approval
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

					<!-- Auto-reply delay -->
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
								Wait before sending an auto-reply, allowing time for follow-up messages. 0 = immediate.
							</span>
						</label>
					{/if}

					<!-- Max email length -->
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
						<span class="text-xs text-text-secondary">
							Maximum character count for generated email bodies
						</span>
					</label>

					<!-- Include greeting -->
					<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
						<div>
							<span class="block text-xs font-medium text-text-primary">Include Greeting</span>
							<span class="block text-[11px] text-text-secondary">
								Start emails with a greeting line (e.g. "Hi John,")
							</span>
						</div>
						<button
							type="button"
							role="switch"
							aria-checked={form.include_greeting}
							onclick={() => (form.include_greeting = !form.include_greeting)}
							class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
								{form.include_greeting ? 'bg-accent' : 'bg-border'}"
						>
							<span
								class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform
									{form.include_greeting ? 'translate-x-5' : 'translate-x-0'}"
							/>
						</button>
					</div>

					<!-- Include sign-off -->
					<div class="flex items-center justify-between rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
						<div>
							<span class="block text-xs font-medium text-text-primary">Include Sign-Off</span>
							<span class="block text-[11px] text-text-secondary">
								End emails with a sign-off line (e.g. "Best regards, Ember")
							</span>
						</div>
						<button
							type="button"
							role="switch"
							aria-checked={form.include_sign_off}
							onclick={() => (form.include_sign_off = !form.include_sign_off)}
							class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
								{form.include_sign_off ? 'bg-accent' : 'bg-border'}"
						>
							<span
								class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform
									{form.include_sign_off ? 'translate-x-5' : 'translate-x-0'}"
							/>
						</button>
					</div>
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- CC Behaviour                                                   -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
					<Users size={16} class="text-ember" />
					CC Behaviour
				</h2>
				<p class="mb-4 text-xs text-text-secondary">
					Control how the agent handles emails where it is CC'd rather than the primary recipient.
				</p>

				<div class="flex flex-col gap-4">
					<!-- Radio buttons -->
					<div class="flex flex-col gap-2">
						<label class="flex items-start gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-secondary/80">
							<input
								type="radio"
								name="cc_mode"
								value="respond_all"
								bind:group={form.cc_mode}
								class="mt-0.5 accent-accent"
							/>
							<div>
								<span class="block text-xs font-medium text-text-primary">Reply All</span>
								<span class="block text-[11px] text-text-secondary">
									Respond to the entire thread, keeping all recipients in the loop
								</span>
							</div>
						</label>

						<label class="flex items-start gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-secondary/80">
							<input
								type="radio"
								name="cc_mode"
								value="respond_sender"
								bind:group={form.cc_mode}
								class="mt-0.5 accent-accent"
							/>
							<div>
								<span class="block text-xs font-medium text-text-primary">Reply to Sender Only</span>
								<span class="block text-[11px] text-text-secondary">
									Respond only to the person who sent the email
								</span>
							</div>
						</label>

						<label class="flex items-start gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-secondary/80">
							<input
								type="radio"
								name="cc_mode"
								value="silent"
								bind:group={form.cc_mode}
								class="mt-0.5 accent-accent"
							/>
							<div>
								<span class="block text-xs font-medium text-text-primary">Silent</span>
								<span class="block text-[11px] text-text-secondary">
									Do not respond when CC'd. The agent will still process the email for context.
								</span>
							</div>
						</label>
					</div>

					<!-- CC instructions -->
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">CC Instructions</span>
						<textarea
							bind:value={form.cc_instructions}
							placeholder="Additional instructions for handling CC'd emails..."
							rows={3}
							class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						></textarea>
						<span class="text-xs text-text-secondary">
							Optional guidance for the agent when it is CC'd on an email
						</span>
					</label>
				</div>
			</section>

			<!-- ============================================================= -->
			<!-- Test Email                                                     -->
			<!-- ============================================================= -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
					<Send size={16} class="text-ember" />
					Send Test Email
				</h2>
				<p class="mb-4 text-xs text-text-secondary">
					Verify your email configuration by sending a test message. Save your settings first.
				</p>

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
			</section>
		</div>
	{/if}
</div>
