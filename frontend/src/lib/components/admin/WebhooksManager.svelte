<!--
  WebhooksManager.svelte — Unified admin for webhook log, outbound callbacks,
  and ngrok tunnel management.

  Three tabs: Log | Callbacks | Tunnel

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
		Power,
		PowerOff,
		Copy,
		CheckCircle,
		AlertCircle,
		Trash2,
		Webhook,
		ArrowUpRight,
		Download,
		Shield,
		Key,
		Package,
		Play,
		Square,
		ExternalLink,
		Mail,
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

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

	interface CallbackConfig {
		id: string;
		url: string;
		secret: string;
		events: string[];
		enabled: boolean;
		created_at: string;
	}

	interface TunnelStatus {
		active: boolean;
		url: string | null;
		available: boolean;
		error: string | null;
	}

	interface PyngrokStatus {
		installed: boolean;
		version: string | null;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const CALLBACK_EVENTS = [
		{ id: 'email.sent', label: 'Email Sent' },
		{ id: 'email.received', label: 'Email Received' },
		{ id: 'email.failed', label: 'Email Failed' },
		{ id: 'conversation.created', label: 'Conversation Created' },
		{ id: 'conversation.updated', label: 'Conversation Updated' },
		{ id: 'agent.error', label: 'Agent Error' },
	];

	// -----------------------------------------------------------------------
	// Tabs
	// -----------------------------------------------------------------------

	type TabId = 'log' | 'callbacks' | 'tunnel';
	let activeTab = $state<TabId>('log');

	const tabs: { id: TabId; label: string; icon: any }[] = [
		{ id: 'log', label: 'Log', icon: Code },
		{ id: 'callbacks', label: 'Callbacks', icon: ArrowUpRight },
		{ id: 'tunnel', label: 'Tunnel', icon: Radio },
	];

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
	// Callback state
	// -----------------------------------------------------------------------

	let callbacks = $state<CallbackConfig[]>([]);
	let callbacksLoading = $state(false);
	let showCallbackModal = $state(false);
	let callbackUrl = $state('');
	let callbackEvents = $state<string[]>([]);
	let editingCallbackId = $state<string | null>(null);
	let testingCallbackId = $state<string | null>(null);
	let callbackTestResult = $state<{ success: boolean; status_code?: number; error?: string } | null>(null);

	// -----------------------------------------------------------------------
	// Tunnel state
	// -----------------------------------------------------------------------

	let tunnelStatus = $state<TunnelStatus>({ active: false, url: null, available: false, error: null });
	let tunnelLoading = $state(false);
	let pyngrokStatus = $state<PyngrokStatus>({ installed: false, version: null });
	let pyngrokInstalling = $state(false);
	let authToken = $state('');
	let authTokenSaved = $state(false);
	let authTokenSaving = $state(false);
	let tunnelUrlCopied = $state(false);
	let tunnelWebhookCopied = $state<string | null>(null);

	// Integrations (auto-detected from settings)
	interface Integration {
		type: string;
		provider: string;
		enabled: boolean;
		webhook_path: string;
	}
	let integrations = $state<Integration[]>([]);

	// Tunnel backends
	interface TunnelBackendInfo {
		id: string;
		label: string;
		available: boolean;
		requires_auth: boolean;
	}
	let tunnelBackends = $state<TunnelBackendInfo[]>([]);
	let selectedBackend = $state('ngrok');

	// -----------------------------------------------------------------------
	// Tunnel readiness
	// -----------------------------------------------------------------------

	let tunnelReady = $derived(
		selectedBackend === 'cloudflared'
			? tunnelBackends.some(b => b.id === 'cloudflared' && b.available)
			: authTokenSaved && pyngrokStatus.installed
	);

	// -----------------------------------------------------------------------
	// Init
	// -----------------------------------------------------------------------

	$effect(() => {
		loadLog();
		loadCallbacks();
		loadTunnelStatus();
		loadPyngrokStatus();
		loadAuthToken();
		loadIntegrations();
		loadTunnelBackends();
	});

	// -----------------------------------------------------------------------
	// Log functions
	// -----------------------------------------------------------------------

	async function loadLog() {
		logLoading = true;
		try {
			const res = await apiJson<{ entries: WebhookLogEntry[] }>('/dev-tools/log?limit=50');
			logEntries = res.entries;
		} catch { /* ignore */ }
		finally { logLoading = false; }
	}

	async function clearLog() {
		try {
			await apiJson('/dev-tools/log', { method: 'DELETE' });
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
			logDetail = await apiJson<WebhookLogEntry>(`/dev-tools/log/${entryId}`);
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
	// Callback functions
	// -----------------------------------------------------------------------

	async function loadCallbacks() {
		callbacksLoading = true;
		try {
			const res = await apiJson<{ callbacks: CallbackConfig[] }>('/callbacks');
			callbacks = res.callbacks || [];
		} catch { /* ignore */ }
		finally { callbacksLoading = false; }
	}

	function openCallbackModal(cb?: CallbackConfig) {
		if (cb) {
			editingCallbackId = cb.id;
			callbackUrl = cb.url;
			callbackEvents = [...cb.events];
		} else {
			editingCallbackId = null;
			callbackUrl = '';
			callbackEvents = [];
		}
		callbackTestResult = null;
		showCallbackModal = true;
	}

	function closeCallbackModal() {
		showCallbackModal = false;
		editingCallbackId = null;
		callbackUrl = '';
		callbackEvents = [];
	}

	async function saveCallback() {
		if (!callbackUrl.trim()) return;
		try {
			if (editingCallbackId) {
				const updated = await apiJson<CallbackConfig>(`/callbacks/${editingCallbackId}`, {
					method: 'PUT',
					body: JSON.stringify({ url: callbackUrl.trim(), events: callbackEvents }),
				});
				callbacks = callbacks.map(cb =>
					cb.id === editingCallbackId ? { ...cb, ...updated } : cb
				);
			} else {
				const created = await apiJson<CallbackConfig>('/callbacks', {
					method: 'POST',
					body: JSON.stringify({ url: callbackUrl.trim(), events: callbackEvents }),
				});
				callbacks = [...callbacks, created];
			}
			closeCallbackModal();
		} catch { /* ignore */ }
	}

	async function deleteCallback(id: string) {
		try {
			await apiJson(`/callbacks/${id}`, { method: 'DELETE' });
			callbacks = callbacks.filter(cb => cb.id !== id);
		} catch { /* ignore */ }
	}

	async function toggleCallbackEnabled(id: string) {
		const cb = callbacks.find(c => c.id === id);
		if (!cb) return;
		try {
			const updated = await apiJson<CallbackConfig>(`/callbacks/${id}`, {
				method: 'PUT',
				body: JSON.stringify({ enabled: !cb.enabled }),
			});
			callbacks = callbacks.map(c => c.id === id ? { ...c, ...updated } : c);
		} catch { /* ignore */ }
	}

	async function testCallback(id: string) {
		testingCallbackId = id;
		callbackTestResult = null;
		try {
			callbackTestResult = await apiJson<{ success: boolean; status_code?: number; error?: string }>(
				`/callbacks/${id}/test`, { method: 'POST' }
			);
		} catch (e) {
			callbackTestResult = { success: false, error: e instanceof Error ? e.message : 'Test failed' };
		} finally {
			testingCallbackId = null;
			setTimeout(() => (callbackTestResult = null), 5000);
		}
	}

	function copySecret(secret: string) {
		navigator.clipboard.writeText(secret);
	}

	// -----------------------------------------------------------------------
	// Tunnel functions
	// -----------------------------------------------------------------------

	async function loadTunnelStatus() {
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/status');
		} catch { /* ignore */ }
	}

	async function loadPyngrokStatus() {
		try {
			pyngrokStatus = await apiJson<PyngrokStatus>('/dev-tools/tunnel/pyngrok-status');
		} catch { /* ignore */ }
	}

	async function loadAuthToken() {
		try {
			const res = await apiJson<{ ngrok_auth_token?: string }>('/settings/email');
			if (res.ngrok_auth_token) {
				authToken = res.ngrok_auth_token;
				authTokenSaved = true;
			}
		} catch { /* ignore */ }
	}

	async function saveAuthToken() {
		if (!authToken.trim()) return;
		authTokenSaving = true;
		try {
			await apiJson('/dev-tools/tunnel/auth-token', {
				method: 'PUT',
				body: JSON.stringify({ auth_token: authToken.trim() }),
			});
			authTokenSaved = true;
		} catch { /* ignore */ }
		finally { authTokenSaving = false; }
	}

	async function installPyngrok() {
		pyngrokInstalling = true;
		try {
			const res = await apiJson<{ success: boolean; error?: string }>('/dev-tools/tunnel/install-pyngrok', {
				method: 'POST',
			});
			if (res.success) {
				await loadPyngrokStatus();
			}
		} catch { /* ignore */ }
		finally { pyngrokInstalling = false; }
	}

	async function startTunnel() {
		tunnelLoading = true;
		tunnelStatus = { ...tunnelStatus, error: null };
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/start', { method: 'POST' });
		} catch (e) {
			tunnelStatus = { ...tunnelStatus, error: e instanceof Error ? e.message : 'Failed to start tunnel' };
		} finally {
			tunnelLoading = false;
		}
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

	function copyTunnelWebhookUrl(webhookPath: string) {
		if (tunnelStatus.url) {
			navigator.clipboard.writeText(`${tunnelStatus.url}${webhookPath}`);
			tunnelWebhookCopied = webhookPath;
			setTimeout(() => (tunnelWebhookCopied = null), 2000);
		}
	}

	async function loadIntegrations() {
		try {
			const res = await apiJson<{ integrations: Integration[] }>('/dev-tools/integrations');
			integrations = res.integrations || [];
		} catch { /* ignore */ }
	}

	async function loadTunnelBackends() {
		try {
			const res = await apiJson<{ backends: TunnelBackendInfo[] }>('/dev-tools/tunnel/backends');
			tunnelBackends = res.backends || [];
		} catch { /* ignore */ }
	}

	async function saveTunnelBackend(backend: string) {
		selectedBackend = backend;
		try {
			await apiJson('/settings/email', {
				method: 'PUT',
				body: JSON.stringify({ tunnel_backend: backend }),
			});
		} catch { /* ignore */ }
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
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 px-6 pt-6 pb-4">
		<div class="mb-4">
			<h1 class="text-lg font-semibold text-text-primary">Webhooks</h1>
			<p class="text-sm text-text-secondary">
				Inbound webhook log, outbound callbacks, and dev tunnel management
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

			<!-- =========================================================== -->
			<!-- CALLBACKS TAB                                                -->
			<!-- =========================================================== -->
			{#if activeTab === 'callbacks'}
				<section class="rounded-lg border border-border bg-surface p-5">
					<div class="mb-3 flex items-center justify-between">
						<h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Globe size={16} class="text-ember" />
							Outbound Callbacks
						</h2>
						<button type="button" onclick={() => openCallbackModal()}
							class="inline-flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover">
							Add Callback
						</button>
					</div>
					<p class="mb-4 text-xs text-text-secondary">
						Register external webhook URLs that receive callbacks when events occur (email sent, received, etc.).
					</p>

					{#if callbacksLoading}
						<div class="flex justify-center py-6">
							<Loader2 size={20} class="animate-spin text-text-secondary" />
						</div>
					{:else if callbacks.length === 0}
						<p class="py-4 text-center text-xs text-text-secondary italic">No callbacks configured yet.</p>
					{:else}
						<div class="flex flex-col gap-3">
							{#each callbacks as cb}
							<div class="rounded-md border border-border p-3">
								<div class="flex items-start justify-between gap-3">
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-2">
											<code class="truncate text-xs text-text-primary">{cb.url}</code>
											<span class="inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium {cb.enabled ? 'bg-success/10 text-success' : 'bg-surface-secondary text-text-secondary'}">
												{cb.enabled ? 'Active' : 'Disabled'}
											</span>
										</div>
										{#if cb.events.length > 0}
										<div class="mt-1.5 flex flex-wrap gap-1">
											{#each cb.events as ev}
											<span class="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">{ev}</span>
											{/each}
										</div>
										{:else}
										<span class="mt-1 text-[10px] text-text-secondary">All events</span>
										{/if}
									</div>
									<div class="flex items-center gap-1.5">
										<button type="button" onclick={() => toggleCallbackEnabled(cb.id)} class="rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-surface-hover">{cb.enabled ? 'Disable' : 'Enable'}</button>
										<button type="button" onclick={() => testCallback(cb.id)} disabled={testingCallbackId === cb.id} class="rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50">{#if testingCallbackId === cb.id}<Loader2 size={10} class="animate-spin" />{:else}Test{/if}</button>
										<button type="button" onclick={() => openCallbackModal(cb)} class="rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-surface-hover">Edit</button>
										<button type="button" onclick={() => deleteCallback(cb.id)} class="rounded-md border border-danger/30 px-2 py-1 text-[11px] text-danger transition-colors hover:bg-danger/10">Delete</button>
									</div>
								</div>
								{#if cb.secret}
								<div class="mt-2 flex items-center gap-2">
									<span class="text-[10px] text-text-secondary">Secret:</span>
									<code class="text-[10px] text-text-secondary">{cb.secret.slice(0, 8)}...</code>
									<button type="button" onclick={() => copySecret(cb.secret)} class="text-[10px] text-accent hover:underline">Copy</button>
								</div>
								{/if}
							</div>
							{/each}
						</div>
					{/if}

					{#if callbackTestResult}
						<div class="mt-3 rounded-md border px-3 py-2 text-xs {callbackTestResult.success ? 'border-success/30 bg-success/5 text-success' : 'border-danger/30 bg-danger/5 text-danger'}">
							{#if callbackTestResult.success}Test payload delivered (status: {callbackTestResult.status_code}){:else}Test failed: {callbackTestResult.error}{/if}
						</div>
					{/if}
				</section>
			{/if}

			<!-- =========================================================== -->
			<!-- TUNNEL TAB                                                   -->
			<!-- =========================================================== -->
			{#if activeTab === 'tunnel'}
				<!-- Backend Selector -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<div class="mb-3">
						<h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Globe size={16} class="text-ember" />
							Tunnel Backend
						</h2>
						<p class="mt-1 text-[11px] text-text-secondary">
							Choose how to expose your local server for webhook delivery.
						</p>
					</div>
					<div class="flex gap-3">
						{#each tunnelBackends as backend}
							<button
								type="button"
								onclick={() => saveTunnelBackend(backend.id)}
								class="flex flex-1 flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors
									{selectedBackend === backend.id ? 'border-accent bg-accent/5' : 'border-border hover:bg-surface-hover'}
									{!backend.available ? 'opacity-50' : ''}"
								disabled={!backend.available}
							>
								<span class="text-xs font-medium text-text-primary">{backend.label}</span>
								<span class="text-[10px] text-text-secondary">
									{#if backend.id === 'ngrok'}
										Requires auth token + pyngrok
									{:else}
										Zero-config, no account needed
									{/if}
								</span>
								{#if !backend.available}
									<span class="text-[10px] text-warning">Not installed</span>
								{/if}
							</button>
						{/each}
					</div>
				</section>

				<!-- ngrok setup (only when ngrok selected) -->
				{#if selectedBackend === 'ngrok'}
				<!-- Step 1: Auth Token -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<div class="mb-3 flex items-center gap-3">
						<div class="flex h-7 w-7 items-center justify-center rounded-full {authTokenSaved ? 'bg-success/10' : 'bg-surface-secondary'}">
							{#if authTokenSaved}
								<CheckCircle size={14} class="text-success" />
							{:else}
								<Key size={14} class="text-text-secondary" />
							{/if}
						</div>
						<div>
							<h2 class="text-sm font-semibold text-text-primary">ngrok Auth Token</h2>
							<p class="text-[11px] text-text-secondary">Required to create tunnels. Get a free token from ngrok.com</p>
						</div>
					</div>

					<div class="flex gap-2">
						<input
							type="password"
							bind:value={authToken}
							placeholder="Enter your ngrok auth token"
							oninput={() => { if (authTokenSaved) authTokenSaved = false; }}
							class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary outline-none transition-colors focus:border-accent"
						/>
						<button
							type="button"
							onclick={saveAuthToken}
							disabled={authTokenSaving || !authToken.trim()}
							class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50
								{authTokenSaved ? 'border border-success/30 bg-success/10 text-success' : 'bg-accent text-white hover:bg-accent-hover'}"
						>
							{#if authTokenSaving}
								<Loader2 size={12} class="animate-spin" />
							{:else if authTokenSaved}
								<CheckCircle size={12} />
								Saved
							{:else}
								Save
							{/if}
						</button>
					</div>
					<p class="mt-2 text-[10px] text-text-secondary">
						Get your free auth token from <a href="https://dashboard.ngrok.com/get-started/your-authtoken" target="_blank" rel="noopener noreferrer" class="text-accent underline">ngrok dashboard</a>.
					</p>
				</section>

				<!-- Step 2: pyngrok Status -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<div class="mb-3 flex items-center gap-3">
						<div class="flex h-7 w-7 items-center justify-center rounded-full {pyngrokStatus.installed ? 'bg-success/10' : 'bg-surface-secondary'}">
							{#if pyngrokStatus.installed}
								<CheckCircle size={14} class="text-success" />
							{:else}
								<Package size={14} class="text-text-secondary" />
							{/if}
						</div>
						<div class="flex-1">
							<h2 class="text-sm font-semibold text-text-primary">pyngrok</h2>
							<p class="text-[11px] text-text-secondary">Python wrapper for ngrok, required for tunnel management</p>
						</div>
						<span class="inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium {pyngrokStatus.installed ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}">
							{pyngrokStatus.installed ? `v${pyngrokStatus.version}` : 'Not installed'}
						</span>
					</div>

					{#if !pyngrokStatus.installed}
						<button
							type="button"
							onclick={installPyngrok}
							disabled={pyngrokInstalling}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if pyngrokInstalling}
								<Loader2 size={12} class="animate-spin" />
								Installing…
							{:else}
								<Download size={12} />
								Install pyngrok
							{/if}
						</button>
						<p class="mt-2 text-[10px] text-text-secondary">
							This will run <code class="rounded bg-surface-secondary px-1">pip install pyngrok</code> in the server's Python environment.
						</p>
					{/if}
				</section>
				{/if}

				<!-- Tunnel Controls -->
				<section class="rounded-lg border {tunnelStatus.active ? 'border-success/30 bg-success/5' : 'border-border bg-surface'} p-5">
					<div class="mb-3 flex items-center gap-3">
						<div class="flex h-7 w-7 items-center justify-center rounded-full {tunnelStatus.active ? 'bg-success/10' : 'bg-surface-secondary'}">
							{#if tunnelStatus.active}
								<Radio size={14} class="text-success" />
							{:else}
								<Radio size={14} class="text-text-secondary" />
							{/if}
						</div>
						<div class="flex-1">
							<h2 class="text-sm font-semibold text-text-primary">Tunnel</h2>
							<p class="text-[11px] text-text-secondary">
								{#if tunnelStatus.active}
									Active — forwarding to localhost
								{:else}
									Expose your local server for webhook delivery
								{/if}
							</p>
						</div>
						{#if tunnelStatus.active}
							<span class="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
								<span class="inline-block h-1.5 w-1.5 rounded-full bg-success animate-pulse"></span>
								Active
							</span>
						{/if}
					</div>

					<div class="flex items-center gap-2">
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
									<Square size={12} />
								{/if}
								Stop Tunnel
							</button>
						{:else}
							<button
								type="button"
								onclick={startTunnel}
								disabled={tunnelLoading || !tunnelReady}
								class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
							>
								{#if tunnelLoading}
									<Loader2 size={12} class="animate-spin" />
									Starting…
								{:else}
									<Play size={12} />
									Start Tunnel
								{/if}
							</button>
							{#if !tunnelReady}
								<span class="text-[11px] text-text-secondary">
									{#if selectedBackend === 'cloudflared'}
										cloudflared not available — install it first
									{:else if !authTokenSaved}
										Save auth token first
									{:else}
										Install pyngrok first
									{/if}
								</span>
							{/if}
						{/if}
					</div>

					{#if tunnelStatus.error}
						<div class="mt-3 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
							{tunnelStatus.error}
						</div>
					{/if}

					{#if tunnelStatus.active && tunnelStatus.url}
						<div class="mt-4 flex flex-col gap-3">
							<!-- Tunnel URL -->
							<div>
								<label class="mb-1 block text-[11px] font-medium text-text-secondary">Tunnel URL</label>
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

							<!-- Webhook URLs (auto-detected) -->
							{#if integrations.length > 0}
								<div>
									<label class="mb-1 block text-[11px] font-medium text-text-secondary">Webhook URLs</label>
									<div class="flex flex-col gap-2">
										{#each integrations as integration}
											<div class="flex items-center gap-2">
												<div class="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-accent/10">
													<Mail size={12} class="text-accent" />
												</div>
												<code class="flex-1 rounded-md border border-success/30 bg-success/5 px-3 py-1.5 text-xs font-medium text-success">
													{tunnelStatus.url}{integration.webhook_path}
												</code>
												<span class="shrink-0 text-[10px] capitalize text-text-secondary">{integration.provider}</span>
												<button
													type="button"
													onclick={() => copyTunnelWebhookUrl(integration.webhook_path)}
													class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
												>
													{#if tunnelWebhookCopied === integration.webhook_path}<CheckCircle size={10} class="text-success" />{:else}<Copy size={10} />{/if}
												</button>
											</div>
										{/each}
									</div>
									<p class="mt-1 text-[10px] text-text-secondary">
										Paste this URL in your email provider's webhook settings.
									</p>
								</div>
							{:else}
								<div class="rounded-md border border-border/50 bg-surface-secondary/20 px-3 py-3 text-center">
									<p class="text-xs text-text-secondary">No integrations configured.</p>
									<a href="/admin/email" class="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
										Configure email integration
										<ExternalLink size={10} />
									</a>
								</div>
							{/if}
						</div>
					{/if}
				</section>
			{/if}

		</div>
	</div>
</div>

<!-- Callback Add/Edit Modal -->
{#if showCallbackModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
		<div class="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-xl">
			<h3 class="mb-4 text-sm font-semibold text-text-primary">
				{editingCallbackId ? 'Edit Callback' : 'Add Callback'}
			</h3>

			<div class="flex flex-col gap-4">
				<div>
					<label class="mb-1 block text-xs font-medium text-text-secondary">Webhook URL</label>
					<input
						type="url"
						bind:value={callbackUrl}
						placeholder="https://example.com/webhook"
						class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
					/>
				</div>

				<div>
					<label class="mb-2 block text-xs font-medium text-text-secondary">Events (leave empty for all)</label>
					<div class="flex flex-wrap gap-2">
						{#each CALLBACK_EVENTS as ev}
							<label class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors cursor-pointer {callbackEvents.includes(ev.id) ? 'border-accent bg-accent/10 text-accent' : 'border-border text-text-secondary hover:bg-surface-hover'}">
								<input
									type="checkbox"
									checked={callbackEvents.includes(ev.id)}
									onchange={() => {
										if (callbackEvents.includes(ev.id)) {
											callbackEvents = callbackEvents.filter(e => e !== ev.id);
										} else {
											callbackEvents = [...callbackEvents, ev.id];
										}
									}}
									class="sr-only"
								/>
								{ev.label}
							</label>
						{/each}
					</div>
				</div>
			</div>

			<div class="mt-6 flex items-center justify-end gap-2">
				<button
					type="button"
					onclick={closeCallbackModal}
					class="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={saveCallback}
					disabled={!callbackUrl.trim()}
					class="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{editingCallbackId ? 'Update' : 'Add Callback'}
				</button>
			</div>
		</div>
	</div>
{/if}
