<!--
  DevToolsManager.svelte — Dev tools dashboard with tunnel status
  and integrations overview. Opens TunnelSetupWizard for configuration.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Loader2,
		Globe,
		Radio,
		Copy,
		CheckCircle,
		Play,
		Square,
		ExternalLink,
		Mail,
		Webhook,
		ArrowUpRight,
		Settings,
		AlertTriangle,
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import TunnelSetupWizard from './TunnelSetupWizard.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface TunnelStatus {
		active: boolean;
		url: string | null;
		available: boolean;
		error: string | null;
		backend?: string;
	}

	interface Integration {
		type: string;
		provider: string;
		enabled: boolean;
		webhook_path: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let tunnelStatus = $state<TunnelStatus>({ active: false, url: null, available: false, error: null });
	let tunnelLoading = $state(false);
	let integrations = $state<Integration[]>([]);
	let loading = $state(true);
	let wizardOpen = $state(false);
	let tunnelUrlCopied = $state(false);
	let tunnelWebhookCopied = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Init
	// -----------------------------------------------------------------------

	$effect(() => {
		loadAll();
	});

	async function loadAll() {
		loading = true;
		await Promise.all([loadTunnelStatus(), loadIntegrations()]);
		loading = false;
	}

	// -----------------------------------------------------------------------
	// API calls
	// -----------------------------------------------------------------------

	async function loadTunnelStatus() {
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/status');
		} catch { /* ignore */ }
	}

	async function loadIntegrations() {
		try {
			const res = await apiJson<{ integrations: Integration[] }>('/dev-tools/integrations');
			integrations = res.integrations || [];
		} catch { /* ignore */ }
	}

	async function stopTunnel() {
		tunnelLoading = true;
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/stop', { method: 'POST' });
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

	function copyWebhookUrl(webhookPath: string) {
		if (tunnelStatus.url) {
			navigator.clipboard.writeText(`${tunnelStatus.url}${webhookPath}`);
			tunnelWebhookCopied = webhookPath;
			setTimeout(() => (tunnelWebhookCopied = null), 2000);
		}
	}

	function onWizardConnected() {
		loadTunnelStatus();
		loadIntegrations();
	}

	function onWizardClose() {
		wizardOpen = false;
		loadTunnelStatus();
	}
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 border-b border-border px-6 py-4">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10">
					<Radio size={18} class="text-accent" />
				</div>
				<div>
					<h1 class="text-base font-semibold text-text-primary">Dev Tools</h1>
					<p class="text-xs text-text-secondary">
						Tunnel management and integrations for local development
					</p>
				</div>
			</div>
			<button
				type="button"
				onclick={() => (wizardOpen = true)}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Settings size={14} />
				{tunnelStatus.active ? 'Tunnel Settings' : 'Setup Tunnel'}
			</button>
		</div>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-y-auto px-6 py-6">
		{#if loading}
			<div class="flex justify-center py-16">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else}
			<div class="mx-auto flex max-w-2xl flex-col gap-6">

				<!-- =========================================================== -->
				<!-- Tunnel Status Card                                           -->
				<!-- =========================================================== -->
				{#if tunnelStatus.active && tunnelStatus.url}
					<!-- Active tunnel -->
					<section class="rounded-xl border border-success/40 bg-success/5 p-5">
						<div class="flex items-center gap-3">
							<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-success/10">
								<Radio size={20} class="text-success" />
							</div>
							<div class="flex-1">
								<div class="flex items-center gap-2">
									<h2 class="text-sm font-semibold text-text-primary">Tunnel Active</h2>
									<span class="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
										<span class="inline-block h-1.5 w-1.5 rounded-full bg-success animate-pulse"></span>
										Connected
									</span>
								</div>
								<p class="text-xs text-text-secondary">
									Using {tunnelStatus.backend || 'ngrok'} — forwarding to localhost:8000
								</p>
							</div>
							<div class="flex items-center gap-2">
								<button
									type="button"
									onclick={() => (wizardOpen = true)}
									class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
								>
									<Settings size={12} />
									Settings
								</button>
								<button
									type="button"
									onclick={stopTunnel}
									disabled={tunnelLoading}
									class="inline-flex items-center gap-1 rounded-md border border-danger/30 bg-danger/10 px-2.5 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/20 disabled:opacity-50"
								>
									{#if tunnelLoading}<Loader2 size={12} class="animate-spin" />{:else}<Square size={12} />{/if}
									Disconnect
								</button>
							</div>
						</div>

						<!-- Public URL -->
						<div class="mt-4">
							<label class="mb-1.5 block text-xs font-medium text-text-secondary">Public URL</label>
							<div class="flex items-center gap-2">
								<code class="flex-1 rounded-lg border border-success/30 bg-white/5 px-4 py-2.5 text-sm font-medium text-success">
									{tunnelStatus.url}
								</code>
								<button
									type="button"
									onclick={copyTunnelUrl}
									class="inline-flex h-[38px] items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
								>
									{#if tunnelUrlCopied}
										<CheckCircle size={12} class="text-success" /> Copied
									{:else}
										<Copy size={12} /> Copy
									{/if}
								</button>
							</div>
						</div>

						<!-- Webhook URLs -->
						{#if integrations.length > 0}
							<div class="mt-4">
								<label class="mb-1.5 block text-xs font-medium text-text-secondary">Webhook Endpoints</label>
								<div class="flex flex-col gap-2">
									{#each integrations as integration}
										<div class="flex items-center gap-2 rounded-lg border border-border/30 bg-white/5 p-3">
											<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent/10">
												<Mail size={14} class="text-accent" />
											</div>
											<div class="flex-1 overflow-hidden">
												<p class="text-xs font-medium capitalize text-text-primary">{integration.provider}</p>
												<code class="block truncate text-[11px] text-text-secondary">
													{tunnelStatus.url}{integration.webhook_path}
												</code>
											</div>
											<button
												type="button"
												onclick={() => copyWebhookUrl(integration.webhook_path)}
												class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
											>
												{#if tunnelWebhookCopied === integration.webhook_path}
													<CheckCircle size={10} class="text-success" />
												{:else}
													<Copy size={10} />
												{/if}
											</button>
										</div>
									{/each}
								</div>
								<p class="mt-2 text-xs text-text-secondary">
									Paste these URLs into your email provider's webhook configuration.
								</p>
							</div>
						{/if}
					</section>
				{:else}
					<!-- Inactive tunnel -->
					<section class="rounded-xl border border-border bg-surface p-8 text-center">
						<div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-surface-secondary">
							<Globe size={28} class="text-text-secondary" />
						</div>
						<h2 class="text-sm font-semibold text-text-primary">No tunnel connected</h2>
						<p class="mx-auto mt-1 max-w-sm text-xs text-text-secondary">
							Set up a tunnel to expose your local development server to the internet for receiving webhook callbacks.
						</p>
						<button
							type="button"
							onclick={() => (wizardOpen = true)}
							class="mt-4 inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
						>
							<Play size={14} />
							Setup Tunnel
						</button>

						{#if tunnelStatus.error}
							<div class="mx-auto mt-4 flex max-w-md items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-left">
								<AlertTriangle size={14} class="mt-0.5 shrink-0 text-danger" />
								<p class="text-xs text-danger">{tunnelStatus.error}</p>
							</div>
						{/if}
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- Integrations                                                 -->
				<!-- =========================================================== -->
				{#if integrations.length > 0}
					<section class="rounded-xl border border-border bg-surface p-5">
						<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Globe size={16} class="text-accent" />
							Integrations
						</h2>
						<div class="flex flex-col gap-2">
							{#each integrations as integration}
								<div class="flex items-center gap-3 rounded-lg border border-border/50 bg-surface-secondary/20 px-4 py-3">
									<div class="flex h-8 w-8 items-center justify-center rounded-md {integration.enabled ? 'bg-accent/10' : 'bg-surface-secondary'}">
										<Mail size={16} class="{integration.enabled ? 'text-accent' : 'text-text-secondary'}" />
									</div>
									<div class="flex-1">
										<span class="text-sm font-medium capitalize text-text-primary">{integration.type} — {integration.provider}</span>
										<code class="ml-2 text-xs text-text-secondary">{integration.webhook_path}</code>
									</div>
									{#if integration.enabled}
										<span class="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
											<span class="inline-block h-1.5 w-1.5 rounded-full bg-success"></span>
											Active
										</span>
									{:else}
										<span class="inline-flex rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">
											Inactive
										</span>
									{/if}
								</div>
							{/each}
						</div>
					</section>
				{/if}

				<!-- =========================================================== -->
				<!-- Cross-link banners                                           -->
				<!-- =========================================================== -->
				<div class="grid grid-cols-2 gap-4">
					<a
						href="/admin/webhooks"
						class="group flex items-center gap-3 rounded-xl border border-border bg-surface p-4 transition-all hover:border-accent/30 hover:bg-surface-hover"
					>
						<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 transition-colors group-hover:bg-accent/20">
							<Webhook size={16} class="text-accent" />
						</div>
						<div class="flex-1">
							<span class="text-sm font-medium text-text-primary">Webhook Logs</span>
							<p class="text-xs text-text-secondary">View inbound webhook events</p>
						</div>
						<ExternalLink size={14} class="text-text-secondary transition-colors group-hover:text-accent" />
					</a>
					<a
						href="/admin/callbacks"
						class="group flex items-center gap-3 rounded-xl border border-border bg-surface p-4 transition-all hover:border-accent/30 hover:bg-surface-hover"
					>
						<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 transition-colors group-hover:bg-accent/20">
							<ArrowUpRight size={16} class="text-accent" />
						</div>
						<div class="flex-1">
							<span class="text-sm font-medium text-text-primary">Callbacks</span>
							<p class="text-xs text-text-secondary">Manage outbound endpoints</p>
						</div>
						<ExternalLink size={14} class="text-text-secondary transition-colors group-hover:text-accent" />
					</a>
				</div>

			</div>
		{/if}
	</div>
</div>

<!-- Tunnel Setup Wizard Modal -->
<TunnelSetupWizard
	open={wizardOpen}
	onClose={onWizardClose}
	onConnected={onWizardConnected}
/>
