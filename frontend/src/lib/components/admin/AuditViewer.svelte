<!--
  AuditViewer.svelte - Audit log viewer with filterable, auto-refreshable table.

  Displays audit events with filters for user_id, event_type, and limit.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { RefreshCw, Loader2, Filter, Clock } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface AuditEvent {
		id: string;
		timestamp: string;
		event_type: string;
		user_id: string;
		action: string;
		detail: Record<string, unknown>;
		conversation_id?: string;
		system_id?: string;
		endpoint_id?: string;
		risk_level?: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let events = $state<AuditEvent[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Filters
	let filterUserId = $state('');
	let filterEventType = $state('');
	let filterLimit = $state(50);

	// Auto-refresh
	let autoRefresh = $state(false);
	let refreshInterval = $state<ReturnType<typeof setInterval> | null>(null);

	const eventTypes = [
		'',
		'tool_call',
		'tool_result',
		'confirmation_requested',
		'confirmation_response',
		'agent_response',
		'auth_login',
		'auth_logout',
		'catalog_change',
		'knowledge_update'
	];

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadEvents() {
		loading = true;
		error = '';
		try {
			const params = new URLSearchParams();
			if (filterUserId) params.set('user_id', filterUserId);
			if (filterEventType) params.set('event_type', filterEventType);
			params.set('limit', String(filterLimit));

			const query = params.toString();
			events = await apiJson<AuditEvent[]>(`/audit/events?${query}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load audit events';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadEvents();
	});

	// Auto-refresh management
	$effect(() => {
		if (autoRefresh) {
			refreshInterval = setInterval(() => {
				loadEvents();
			}, 10_000);
		} else if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}

		return () => {
			if (refreshInterval) {
				clearInterval(refreshInterval);
			}
		};
	});

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function formatTimestamp(ts: string): string {
		const d = new Date(ts);
		return d.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: false
		});
	}

	function formatDetail(detail: Record<string, unknown>): string {
		if (!detail || Object.keys(detail).length === 0) return '--';
		return JSON.stringify(detail);
	}

	function truncate(text: string, maxLen: number = 80): string {
		if (!text) return '--';
		return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
	}

	function eventTypeColor(type: string): string {
		if (type.startsWith('auth_')) return 'bg-accent/10 text-accent';
		if (type === 'tool_call' || type === 'tool_result') return 'bg-warning/10 text-warning';
		if (type === 'agent_response') return 'bg-success/10 text-success';
		if (type.includes('confirmation')) return 'bg-danger/10 text-danger';
		if (type === 'catalog_change') return 'bg-accent/10 text-accent';
		if (type === 'knowledge_update') return 'bg-success/10 text-success';
		return 'bg-text-secondary/10 text-text-secondary';
	}

	function formatEventType(type: string): string {
		return type.replace(/_/g, ' ');
	}

	function applyFilters() {
		loadEvents();
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Audit Log</h1>
			<p class="text-sm text-text-secondary">Review system activity and security events</p>
		</div>
		<div class="flex items-center gap-2">
			<!-- Auto-refresh toggle -->
			<label class="flex items-center gap-1.5 text-sm text-text-secondary">
				<input
					type="checkbox"
					bind:checked={autoRefresh}
					class="accent-accent"
				/>
				Auto-refresh
			</label>

			<button
				type="button"
				onclick={() => loadEvents()}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			>
				<RefreshCw size={14} />
				Refresh
			</button>
		</div>
	</div>

	<!-- Filters -->
	<div class="flex items-end gap-3 rounded-lg border border-border bg-surface p-3">
		<div class="flex items-center gap-1.5 text-xs font-medium text-text-secondary">
			<Filter size={14} />
			Filters
		</div>

		<label class="flex flex-col gap-1">
			<span class="text-xs text-text-secondary">User ID</span>
			<input
				type="text"
				bind:value={filterUserId}
				placeholder="All users"
				class="w-40 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
			/>
		</label>

		<label class="flex flex-col gap-1">
			<span class="text-xs text-text-secondary">Event Type</span>
			<select
				bind:value={filterEventType}
				class="w-44 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
			>
				<option value="">All types</option>
				{#each eventTypes.slice(1) as type}
					<option value={type}>{formatEventType(type)}</option>
				{/each}
			</select>
		</label>

		<label class="flex flex-col gap-1">
			<span class="text-xs text-text-secondary">Limit</span>
			<select
				bind:value={filterLimit}
				class="w-20 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
			>
				<option value={25}>25</option>
				<option value={50}>50</option>
				<option value={100}>100</option>
				<option value={200}>200</option>
			</select>
		</label>

		<button
			type="button"
			onclick={applyFilters}
			class="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			Apply
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="rounded-lg border border-border bg-surface">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Timestamp</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Event Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">User</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Action</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Details</th>
						</tr>
					</thead>
					<tbody>
						{#each events as event, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="whitespace-nowrap px-4 py-2">
									<span class="inline-flex items-center gap-1 text-xs text-text-secondary">
										<Clock size={12} />
										{formatTimestamp(event.timestamp)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {eventTypeColor(event.event_type)}"
									>
										{formatEventType(event.event_type)}
									</span>
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{event.user_id}
								</td>
								<td class="px-4 py-2 text-text-primary">{event.action}</td>
								<td class="max-w-xs px-4 py-2 text-xs text-text-secondary" title={formatDetail(event.detail)}>
									{truncate(formatDetail(event.detail))}
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="5" class="px-4 py-8 text-center text-sm text-text-secondary">
									No audit events match the current filters.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Footer summary -->
		<div class="text-xs text-text-secondary">
			Showing {events.length} event{events.length !== 1 ? 's' : ''}
			{#if autoRefresh}
				-- auto-refreshing every 10s
			{/if}
		</div>
	{/if}
</div>
