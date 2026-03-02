<!--
  CallbacksManager.svelte — Admin page for managing outbound callback
  endpoints and viewing delivery history.

  Two tabs: Endpoints | Delivery Log

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Loader2,
		RotateCcw,
		Globe,
		Activity,
		Copy,
		CheckCircle,
		Trash2,
		Radio,
		ArrowUpRight,
		ExternalLink,
		Webhook,
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface CallbackConfig {
		id: string;
		url: string;
		secret: string;
		events: string[];
		enabled: boolean;
		created_at: string;
	}

	interface DeliveryEntry {
		id: string;
		callback_id: string;
		event: string;
		url: string;
		attempt: number;
		status: 'success' | 'failed';
		status_code: number;
		error: string | null;
		payload: Record<string, unknown>;
		created_at: string;
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
		{ id: 'conversation.closed', label: 'Conversation Closed' },
		{ id: 'document.indexed', label: 'Document Indexed' },
		{ id: 'document.deleted', label: 'Document Deleted' },
		{ id: 'knowledge.updated', label: 'Knowledge Updated' },
		{ id: 'agent.error', label: 'Agent Error' },
	];

	// -----------------------------------------------------------------------
	// Tabs
	// -----------------------------------------------------------------------

	type TabId = 'endpoints' | 'delivery-log';
	let activeTab = $state<TabId>('endpoints');

	const tabs: { id: TabId; label: string; icon: any }[] = [
		{ id: 'endpoints', label: 'Endpoints', icon: Globe },
		{ id: 'delivery-log', label: 'Delivery Log', icon: Activity },
	];

	// -----------------------------------------------------------------------
	// Endpoints state
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
	// Delivery Log state
	// -----------------------------------------------------------------------

	let deliveryEntries = $state<DeliveryEntry[]>([]);
	let deliveryLoading = $state(false);
	let deliveryAutoRefresh = $state(false);
	let deliveryAutoInterval: ReturnType<typeof setInterval> | null = null;
	let deliveryFilterStatus = $state<'' | 'success' | 'failed'>('');
	let deliveryFilterEvent = $state('');

	// -----------------------------------------------------------------------
	// Init
	// -----------------------------------------------------------------------

	$effect(() => {
		loadCallbacks();
		loadDeliveryLog();
	});

	// Clean up auto-refresh interval on destroy
	$effect(() => {
		return () => {
			if (deliveryAutoInterval) {
				clearInterval(deliveryAutoInterval);
				deliveryAutoInterval = null;
			}
		};
	});

	// -----------------------------------------------------------------------
	// Callback (Endpoints) functions
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
	// Delivery Log functions
	// -----------------------------------------------------------------------

	async function loadDeliveryLog() {
		deliveryLoading = true;
		try {
			const params = new URLSearchParams({ limit: '50' });
			if (deliveryFilterStatus) params.set('status', deliveryFilterStatus);
			if (deliveryFilterEvent) params.set('event', deliveryFilterEvent);
			const res = await apiJson<{ entries: DeliveryEntry[] }>(`/callbacks/delivery-log?${params}`);
			deliveryEntries = res.entries || [];
		} catch { /* ignore */ }
		finally { deliveryLoading = false; }
	}

	function toggleDeliveryAutoRefresh() {
		deliveryAutoRefresh = !deliveryAutoRefresh;
		if (deliveryAutoRefresh) {
			loadDeliveryLog();
			deliveryAutoInterval = setInterval(loadDeliveryLog, 10000);
		} else if (deliveryAutoInterval) {
			clearInterval(deliveryAutoInterval);
			deliveryAutoInterval = null;
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

	function truncateUrl(url: string, maxLen: number = 50): string {
		if (url.length <= maxLen) return url;
		return url.slice(0, maxLen) + '...';
	}
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="shrink-0 px-6 pt-6 pb-4">
		<div class="mb-4">
			<h1 class="text-lg font-semibold text-text-primary">Callbacks</h1>
			<p class="text-sm text-text-secondary">
				Manage outbound webhook callbacks and view delivery history
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
						<div class="py-6 text-center">
							<div class="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-surface-secondary">
								<ArrowUpRight size={20} class="text-text-secondary" />
							</div>
							<h3 class="text-sm font-semibold text-text-primary">No callbacks configured</h3>
							<p class="mt-1 text-xs text-text-secondary">
								Add an endpoint to receive real-time notifications when events like emails, conversations, or document changes occur.
							</p>
							<button
								type="button"
								onclick={() => openCallbackModal()}
								class="mt-3 inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
							>
								Add Your First Callback
							</button>
						</div>
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
			<!-- DELIVERY LOG TAB                                             -->
			<!-- =========================================================== -->
			{#if activeTab === 'delivery-log'}
				<section class="rounded-lg border border-border bg-surface p-5">
					<div class="mb-3 flex items-center justify-between">
						<h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Activity size={16} class="text-ember" />
							Delivery Log
						</h2>
						<div class="flex items-center gap-2">
							<button type="button" onclick={toggleDeliveryAutoRefresh}
								class="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-colors {deliveryAutoRefresh ? 'border-success/30 bg-success/10 text-success' : 'border-border text-text-secondary hover:bg-surface-hover'}">
								<Radio size={10} />
								Auto
							</button>
							<button type="button" onclick={loadDeliveryLog} disabled={deliveryLoading}
								class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50">
								{#if deliveryLoading}<Loader2 size={10} class="animate-spin" />{:else}<RotateCcw size={10} />{/if}
								Refresh
							</button>
						</div>
					</div>

					<!-- Filters -->
					<div class="mb-4 flex items-center gap-3">
						<div class="flex items-center gap-1.5">
							<label for="filter-status" class="text-[11px] text-text-secondary">Status:</label>
							<select
								id="filter-status"
								bind:value={deliveryFilterStatus}
								onchange={loadDeliveryLog}
								class="rounded-md border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none transition-colors focus:border-accent"
							>
								<option value="">All</option>
								<option value="success">Success</option>
								<option value="failed">Failed</option>
							</select>
						</div>
						<div class="flex items-center gap-1.5">
							<label for="filter-event" class="text-[11px] text-text-secondary">Event:</label>
							<select
								id="filter-event"
								bind:value={deliveryFilterEvent}
								onchange={loadDeliveryLog}
								class="rounded-md border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none transition-colors focus:border-accent"
							>
								<option value="">All</option>
								{#each CALLBACK_EVENTS as ev}
									<option value={ev.id}>{ev.label}</option>
								{/each}
							</select>
						</div>
					</div>

					{#if deliveryLoading && deliveryEntries.length === 0}
						<div class="flex justify-center py-6">
							<Loader2 size={20} class="animate-spin text-text-secondary" />
						</div>
					{:else if deliveryEntries.length === 0}
						<p class="py-6 text-center text-xs text-text-secondary italic">
							No delivery log entries yet. Callback deliveries will appear here when events are dispatched.
						</p>
					{:else}
						<div class="overflow-hidden rounded-md border border-border">
							<table class="w-full text-xs">
								<thead>
									<tr class="border-b border-border bg-surface-secondary/30">
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Time</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Event</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">URL</th>
										<th class="px-3 py-2 text-center font-medium text-text-secondary">Attempt</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Status</th>
										<th class="px-3 py-2 text-center font-medium text-text-secondary">HTTP Code</th>
										<th class="px-3 py-2 text-left font-medium text-text-secondary">Error</th>
									</tr>
								</thead>
								<tbody>
									{#each deliveryEntries as entry}
									<tr class="border-b border-border/50 transition-colors hover:bg-surface-hover">
										<td class="px-3 py-2 text-text-secondary whitespace-nowrap">{relativeTime(entry.created_at)}</td>
										<td class="px-3 py-2 text-text-primary">
											<span class="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">{entry.event}</span>
										</td>
										<td class="px-3 py-2 text-text-primary max-w-[200px] truncate" title={entry.url}>
											<code class="text-[11px]">{truncateUrl(entry.url)}</code>
										</td>
										<td class="px-3 py-2 text-center text-text-secondary">{entry.attempt}</td>
										<td class="px-3 py-2">
											<span class="inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium
												{entry.status === 'success' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}">
												{entry.status}
											</span>
										</td>
										<td class="px-3 py-2 text-center text-text-secondary">{entry.status_code || '-'}</td>
										<td class="px-3 py-2 text-danger max-w-[200px] truncate" title={entry.error || ''}>
											{entry.error || '-'}
										</td>
									</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</section>
			{/if}

			<!-- Cross-link -->
			<a
				href="/admin/webhooks"
				class="flex items-center gap-3 rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-hover"
			>
				<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
					<Webhook size={14} class="text-accent" />
				</div>
				<div class="flex-1">
					<span class="text-xs font-semibold text-text-primary">Inbound Webhooks</span>
					<p class="text-[10px] text-text-secondary">View webhook endpoints and incoming event log</p>
				</div>
				<ExternalLink size={14} class="text-text-secondary" />
			</a>

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
