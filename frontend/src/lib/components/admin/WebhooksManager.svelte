<!--
  WebhooksManager.svelte — Inbound webhook endpoint management and log viewer.

  Two tabs: Endpoints | Log

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Loader2,
		RotateCcw,
		Code,
		Globe,
		Radio,
		Copy,
		CheckCircle,
		Trash2,
		Shield,
		ShieldCheck,
		ExternalLink,
		Mail,
		Webhook,
		ArrowUpRight,
		AlertTriangle,
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface WebhookEndpoint {
		provider: string;
		webhook_path: string;
		signature_verification: boolean;
		enabled: boolean;
	}

	interface WebhookLogEntry {
		id: string;
		timestamp: string;
		provider: string;
		status: string;
		from_address: string;
		subject: string;
		processing_time_ms: number;
		error: string | null;
		payload_preview?: string;
	}

	interface TunnelStatus {
		active: boolean;
		url: string | null;
	}

	// -----------------------------------------------------------------------
	// Tabs
	// -----------------------------------------------------------------------

	type TabId = 'endpoints' | 'log';
	let activeTab = $state<TabId>('endpoints');

	const tabs: { id: TabId; label: string; icon: any }[] = [
		{ id: 'endpoints', label: 'Endpoints', icon: Globe },
		{ id: 'log', label: 'Log', icon: Code },
	];

	// -----------------------------------------------------------------------
	// Endpoints state
	// -----------------------------------------------------------------------

	let endpoints = $state<WebhookEndpoint[]>([]);
	let endpointsLoading = $state(false);
	let endpointsError = $state('');
	let emailEnabled = $state(true);
	let tunnelStatus = $state<TunnelStatus>({ active: false, url: null });
	let copiedPath = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Log state
	// -----------------------------------------------------------------------

	let logEntries = $state<WebhookLogEntry[]>([]);
	let logLoading = $state(false);
	let logAutoRefresh = $state(false);
	let logAutoInterval: ReturnType<typeof setInterval> | null = null;
	let logExpandedId = $state<string | null>(null);
	let logDetail = $state<WebhookLogEntry | null>(null);

	// -----------------------------------------------------------------------
	// Init
	// -----------------------------------------------------------------------

	$effect(() => {
		loadEndpoints();
		loadTunnelStatus();
		loadLog();
	});

	$effect(() => {
		return () => {
			if (logAutoInterval) {
				clearInterval(logAutoInterval);
				logAutoInterval = null;
			}
		};
	});

	// -----------------------------------------------------------------------
	// Endpoints functions
	// -----------------------------------------------------------------------

	async function loadEndpoints() {
		endpointsLoading = true;
		endpointsError = '';
		try {
			const res = await apiJson<{ endpoints: WebhookEndpoint[]; email_enabled: boolean }>('/webhook-admin/endpoints');
			endpoints = res.endpoints || [];
			emailEnabled = res.email_enabled ?? true;
		} catch (e) {
			endpointsError = e instanceof Error ? e.message : 'Failed to load endpoints';
		} finally { endpointsLoading = false; }
	}

	async function loadTunnelStatus() {
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/status');
		} catch { /* ignore */ }
	}

	function getFullUrl(webhookPath: string): string {
		if (tunnelStatus.active && tunnelStatus.url) {
			return `${tunnelStatus.url}${webhookPath}`;
		}
		return webhookPath;
	}

	function copyUrl(webhookPath: string) {
		const url = getFullUrl(webhookPath);
		navigator.clipboard.writeText(url);
		copiedPath = webhookPath;
		setTimeout(() => (copiedPath = null), 2000);
	}

	// -----------------------------------------------------------------------
	// Log functions
	// -----------------------------------------------------------------------

	async function loadLog() {
		logLoading = true;
		try {
			const res = await apiJson<{ entries: WebhookLogEntry[] }>('/webhook-admin/log?limit=50');
			logEntries = res.entries;
		} catch { /* ignore */ }
		finally { logLoading = false; }
	}

	async function clearLog() {
		try {
			await apiJson('/webhook-admin/log', { method: 'DELETE' });
			logEntries = [];
		} catch { /* ignore */ }
	}

	async function expandLogEntry(entryId: string) {
		if (logExpandedId === entryId) {
			logExpandedId = null;
			logDetail = null;
			return;
		}
		logExpandedId = entryId;
		try {
			logDetail = await apiJson<WebhookLogEntry>(`/webhook-admin/log/${entryId}`);
		} catch { logDetail = null; }
	}

	function toggleLogAutoRefresh() {
		logAutoRefresh = !logAutoRefresh;
		if (logAutoRefresh) {
			loadLog();
			logAutoInterval = setInterval(loadLog, 10000);
		} else if (logAutoInterval) {
			clearInterval(logAutoInterval);
			logAutoInterval = null;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function relativeTime(isoString: string): string {
		const now = Date.now();
		const then = new Date(isoString).getTime();
		const diff = Math.floor((now - then) / 1000);
		if (diff < 60) return `${diff}s ago`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return `${Math.floor(diff / 86400)}d ago`;
	}

	function providerLabel(provider: string): string {
		const labels: Record<string, string> = {
			resend: 'Resend',
			sendgrid: 'SendGrid',
			ses: 'Amazon SES',
		};
		return labels[provider] || provider;
	}
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 px-6 pt-6 pb-4">
		<div class="mb-4">
			<h1 class="text-lg font-semibold text-text-primary">Webhooks</h1>
			<p class="text-sm text-text-secondary">
				Manage inbound webhook endpoints and view incoming event log
			</p>
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

	<!-- Tab content -->
	<div class="flex-1 overflow-y-auto px-6 py-6">
		<div class="flex flex-col gap-6">

			<!-- =========================================================== -->
			<!-- ENDPOINTS TAB                                                -->
			<!-- =========================================================== -->
			{#if activeTab === 'endpoints'}
				{#if endpointsError}
					<div class="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3">
						<AlertTriangle size={16} class="shrink-0 text-red-500" />
						<p class="flex-1 text-xs text-text-primary">{endpointsError}</p>
						<button onclick={() => loadEndpoints()} class="text-xs font-medium text-accent hover:underline">Retry</button>
					</div>
				{/if}
				{#if endpointsLoading}
					<div class="flex justify-center py-10">
						<Loader2 size={20} class="animate-spin text-text-secondary" />
					</div>
				{:else if endpoints.length === 0 && !endpointsError}
					<section class="rounded-lg border border-border bg-surface p-6 text-center">
						<div class="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-surface-secondary">
							<Mail size={20} class="text-text-secondary" />
						</div>
						<h2 class="text-sm font-semibold text-text-primary">No email provider configured</h2>
						<p class="mt-1 text-xs text-text-secondary">
							Set up an email provider to start receiving inbound webhooks.
						</p>
						<a href="/admin/email" class="mt-3 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
							Set Up Email
							<ExternalLink size={10} />
						</a>
					</section>
				{:else}
					<!-- Disabled banner -->
					{#if !emailEnabled}
						<div class="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3">
							<AlertTriangle size={16} class="shrink-0 text-warning" />
							<div class="flex-1">
								<p class="text-xs font-medium text-text-primary">Email channel is disabled</p>
								<p class="text-[11px] text-text-secondary">
									Webhooks are configured but won't process incoming emails until the channel is enabled.
								</p>
							</div>
							<a href="/admin/email" class="inline-flex items-center gap-1 rounded-md border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-xs font-medium text-warning transition-colors hover:bg-warning/20">
								Enable in Email Settings
								<ExternalLink size={10} />
							</a>
						</div>
					{/if}

					<section class="flex flex-col gap-3">
						{#each endpoints as endpoint}
							<div class="rounded-lg border {endpoint.enabled ? 'border-border' : 'border-border/50'} bg-surface p-4 {!endpoint.enabled ? 'opacity-80' : ''}">
								<div class="flex items-start justify-between gap-3">
									<div class="flex items-center gap-3">
										<div class="flex h-9 w-9 items-center justify-center rounded-lg {endpoint.enabled ? 'bg-accent/10' : 'bg-surface-secondary'}">
											<Webhook size={18} class="{endpoint.enabled ? 'text-accent' : 'text-text-secondary'}" />
										</div>
										<div>
											<div class="flex items-center gap-2">
												<span class="text-sm font-semibold text-text-primary">{providerLabel(endpoint.provider)}</span>
												{#if endpoint.enabled}
													<span class="inline-flex rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">Active</span>
												{:else}
													<span class="inline-flex rounded-full bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-warning">Inactive</span>
												{/if}
											</div>
											<p class="mt-0.5 text-[11px] text-text-secondary">Inbound email webhook</p>
										</div>
									</div>
									<div class="flex items-center gap-2">
										{#if endpoint.signature_verification}
											<span class="inline-flex items-center gap-1 rounded-md border border-success/20 bg-success/5 px-2 py-1 text-[10px] font-medium text-success">
												<ShieldCheck size={10} />
												Signature Verified
											</span>
										{:else}
											<span class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-text-secondary">
												<Shield size={10} />
												No Signature
											</span>
										{/if}
									</div>
								</div>

								<!-- Webhook URL -->
								<div class="mt-3">
									<label class="mb-1 block text-[11px] font-medium text-text-secondary">Webhook URL</label>
									<div class="flex items-center gap-2">
										<code class="flex-1 rounded-md border border-border bg-surface-secondary/30 px-3 py-1.5 text-xs text-text-primary">
											{getFullUrl(endpoint.webhook_path)}
										</code>
										<button
											type="button"
											onclick={() => copyUrl(endpoint.webhook_path)}
											class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
										>
											{#if copiedPath === endpoint.webhook_path}<CheckCircle size={10} class="text-success" />{:else}<Copy size={10} />{/if}
										</button>
									</div>
									{#if !tunnelStatus.active}
										<p class="mt-1 text-[10px] text-text-secondary">
											Showing relative path. <a href="/admin/dev-tools" class="text-accent hover:underline">Start a tunnel</a> to get a public URL.
										</p>
									{/if}
								</div>
							</div>
						{/each}
					</section>
				{/if}
			{/if}

			<!-- =========================================================== -->
			<!-- LOG TAB                                                      -->
			<!-- =========================================================== -->
			{#if activeTab === 'log'}
				<section class="rounded-lg border border-border bg-surface p-5">
					<div class="mb-3 flex items-center justify-between">
						<h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Code size={16} class="text-ember" />
							Webhook Log
						</h2>
						<div class="flex items-center gap-2">
							<button type="button" onclick={toggleLogAutoRefresh}
								class="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-colors {logAutoRefresh ? 'border-success/30 bg-success/10 text-success' : 'border-border text-text-secondary hover:bg-surface-hover'}">
								<Radio size={10} />
								Auto
							</button>
							<button type="button" onclick={loadLog} disabled={logLoading}
								class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50">
								{#if logLoading}<Loader2 size={10} class="animate-spin" />{:else}<RotateCcw size={10} />{/if}
								Refresh
							</button>
							{#if logEntries.length > 0}
								<button type="button" onclick={clearLog}
									class="inline-flex items-center gap-1 rounded-md border border-danger/30 px-2 py-1 text-[11px] text-danger transition-colors hover:bg-danger/10">
									<Trash2 size={10} /> Clear
								</button>
							{/if}
						</div>
					</div>

					{#if logEntries.length === 0}
						<p class="py-6 text-center text-xs text-text-secondary italic">
							No webhook events yet. Send a test inbound email to see events appear here.
						</p>
					{:else}
						<div class="overflow-hidden rounded-md border border-border">
							<table class="w-full text-xs">
								<thead>
									<tr class="border-b border-border bg-surface-secondary/30">
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Time</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Provider</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">From</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Subject</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Status</th>
										<th class="px-3 py-2 text-right font-medium text-text-secondary">Duration</th>
									</tr>
								</thead>
								<tbody>
									{#each logEntries as entry}
									<tr class="border-b border-border/50 transition-colors hover:bg-surface-hover cursor-pointer" onclick={() => expandLogEntry(entry.id)}>
										<td class="px-3 py-2 text-text-secondary">{relativeTime(entry.timestamp)}</td>
										<td class="px-3 py-2 text-text-primary">{entry.provider}</td>
										<td class="px-3 py-2 text-text-primary max-w-[150px] truncate">{entry.from_address || '-'}</td>
										<td class="px-3 py-2 text-text-primary max-w-[200px] truncate">{entry.subject || '-'}</td>
										<td class="px-3 py-2">
											<span class="inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium
												{entry.status === 'processed' ? 'bg-success/10 text-success' : entry.status === 'skipped' ? 'bg-warning/10 text-warning' : entry.status === 'error' ? 'bg-danger/10 text-danger' : 'bg-accent/10 text-accent'}">
												{entry.status}
											</span>
										</td>
										<td class="px-3 py-2 text-right text-text-secondary">{entry.processing_time_ms}ms</td>
									</tr>
									{#if logExpandedId === entry.id && logDetail}
									<tr>
										<td colspan="6" class="border-b border-border bg-surface-secondary/20 px-3 py-3">
											<div class="text-[11px]">
												{#if logDetail.error}<div class="mb-2 text-danger"><strong>Error:</strong> {logDetail.error}</div>{/if}
												<div class="font-medium text-text-secondary mb-1">Payload Preview:</div>
												<pre class="overflow-x-auto rounded bg-surface p-2 text-[10px] text-text-secondary">{logDetail.payload_preview || 'No payload data'}</pre>
											</div>
										</td>
									</tr>
									{/if}
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</section>
			{/if}

			<!-- Cross-links -->
			<div class="flex gap-3">
				<a
					href="/admin/callbacks"
					class="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-hover"
				>
					<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
						<ArrowUpRight size={14} class="text-accent" />
					</div>
					<div class="flex-1">
						<span class="text-xs font-semibold text-text-primary">Outbound Callbacks</span>
						<p class="text-[10px] text-text-secondary">Manage callback endpoints and delivery log</p>
					</div>
					<ExternalLink size={14} class="text-text-secondary" />
				</a>
				<a
					href="/admin/dev-tools"
					class="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-hover"
				>
					<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
						<Radio size={14} class="text-accent" />
					</div>
					<div class="flex-1">
						<span class="text-xs font-semibold text-text-primary">Dev Tools</span>
						<p class="text-[10px] text-text-secondary">Set up a tunnel for local webhook testing</p>
					</div>
					<ExternalLink size={14} class="text-text-secondary" />
				</a>
			</div>

		</div>
	</div>
</div>
