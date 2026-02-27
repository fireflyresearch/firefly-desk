<!--
  AuditViewer.svelte - Audit log viewer with filterable, auto-refreshable table.

  Displays audit events with filters for user_id, event_type, and limit.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { RefreshCw, Loader2, Filter, Clock, ChevronRight, ChevronDown, ExternalLink, Shield } from 'lucide-svelte';
	import { slide } from 'svelte/transition';
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
	let filterRiskLevel = $state('');
	let filterLimit = $state(50);

	const riskLevels = ['', 'info', 'low', 'medium', 'high', 'critical'] as const;

	// Expanded row
	let expandedEventId = $state<string | null>(null);
	let expandedDetail = $state<AuditEvent | null>(null);
	let loadingDetail = $state(false);

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
		'knowledge_update',
		'message_feedback'
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
			if (filterRiskLevel) params.set('risk_level', filterRiskLevel);
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

	function formatRelativeTime(ts: string): string {
		const d = new Date(ts);
		const now = new Date();
		const diffMs = now.getTime() - d.getTime();
		const diffSec = Math.floor(diffMs / 1000);
		const diffMin = Math.floor(diffSec / 60);
		const diffHr = Math.floor(diffMin / 60);
		const diffDays = Math.floor(diffHr / 24);
		if (diffSec < 60) return 'just now';
		if (diffMin < 60) return `${diffMin}m ago`;
		if (diffHr < 24) return `${diffHr}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	function formatFullTimestamp(ts: string): string {
		const d = new Date(ts);
		return d.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: false
		});
	}

	function riskLevelColor(level?: string): string {
		switch (level) {
			case 'critical': return 'bg-danger/15 text-danger';
			case 'high': return 'bg-orange-500/15 text-orange-400';
			case 'medium': return 'bg-warning/15 text-warning';
			case 'low': return 'bg-accent/15 text-accent';
			case 'info': return 'bg-text-secondary/10 text-text-secondary';
			default: return '';
		}
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
		if (type === 'message_feedback') return 'bg-purple-500/10 text-purple-400';
		return 'bg-text-secondary/10 text-text-secondary';
	}

	function formatEventType(type: string): string {
		return type.replace(/_/g, ' ');
	}

	// -----------------------------------------------------------------------
	// Expand / collapse
	// -----------------------------------------------------------------------

	async function toggleEventExpand(eventId: string) {
		if (expandedEventId === eventId) {
			expandedEventId = null;
			expandedDetail = null;
			return;
		}
		expandedEventId = eventId;
		loadingDetail = true;
		try {
			expandedDetail = await apiJson<AuditEvent>(`/audit/events/${eventId}`);
		} catch {
			// Fall back to inline detail from the list
			expandedDetail = events.find((ev) => ev.id === eventId) ?? null;
		} finally {
			loadingDetail = false;
		}
	}

	function riskLevelBadge(level?: string): string {
		switch (level) {
			case 'high':
				return 'bg-danger/15 text-danger border-danger/30';
			case 'medium':
				return 'bg-warning/15 text-warning border-warning/30';
			case 'low':
				return 'bg-success/15 text-success border-success/30';
			default:
				return 'bg-text-secondary/10 text-text-secondary border-text-secondary/20';
		}
	}

	function formatDetailByType(event: AuditEvent | null): [string, string][] {
		if (!event?.detail) return [];
		const d = event.detail;

		switch (event.event_type) {
			case 'tool_call':
				return [
					['Tool', String(d.tool_name ?? d.tool ?? '--')],
					['Call ID', String(d.call_id ?? '--')],
					['Arguments', d.arguments ? JSON.stringify(d.arguments) : (d.params ? JSON.stringify(d.params) : '--')]
				];
			case 'tool_result':
				return ([
					['Tool', String(d.tool_name ?? d.tool ?? '--')],
					['Success', d.success !== undefined ? String(d.success) : '--'],
					['Status Code', d.status_code ? String(d.status_code) : (d.status ? String(d.status) : '--')],
					['Duration', d.duration_ms ? `${d.duration_ms}ms` : '--'],
					['Error', d.error ? String(d.error) : '']
				] as [string, string][]).filter(([, v]) => v !== '');
			case 'auth_login':
				return [
					['Method', String(d.method ?? '--')],
					['IP Address', String(d.ip ?? '--')],
					['Success', String(d.success ?? '--')]
				];
			case 'auth_logout':
				return [
					['IP Address', String(d.ip ?? '--')]
				];
			case 'agent_response':
				return ([
					['Model', String(d.model ?? '--')],
					['Input Tokens', d.input_tokens ? Number(d.input_tokens).toLocaleString() : '--'],
					['Output Tokens', d.output_tokens ? Number(d.output_tokens).toLocaleString() : '--'],
					['Latency', d.latency_ms ? `${Number(d.latency_ms).toLocaleString()}ms` : '--'],
					['Cost', d.cost_usd ? `$${Number(d.cost_usd).toFixed(4)}` : ''],
					['Message Length', d.message_length ? Number(d.message_length).toLocaleString() : ''],
					['Response Length', d.response_length ? Number(d.response_length).toLocaleString() : '']
				] as [string, string][]).filter(([, v]) => v !== '');
			case 'confirmation_requested':
			case 'confirmation_response':
				return [
					['Action', String(d.action ?? '--')],
					['Status', String(d.status ?? '--')],
					['Message', String(d.message ?? '--')]
				];
			case 'catalog_change':
				return ([
					['Entity', String(d.entity ?? '--')],
					['Operation', String(d.operation ?? '--')],
					['Entity ID', String(d.entity_id ?? '--')],
					['Name', d.name ? String(d.name) : '']
				] as [string, string][]).filter(([, v]) => v !== '');
			case 'knowledge_update':
				return [
					['Source', String(d.source ?? '--')],
					['Operation', String(d.operation ?? '--')],
					['Items', String(d.items_count ?? '--')]
				];
			case 'message_feedback':
				return ([
					['Message ID', String(d.message_id ?? '--')],
					['Rating', String(d.rating ?? '--')],
					['Categories', Array.isArray(d.categories) ? d.categories.join(', ') : '--'],
					['Comment', d.comment ? String(d.comment) : '']
				] as [string, string][]).filter(([, v]) => v !== '');
			default:
				return Object.entries(d).map(([k, v]) => [
					k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
					typeof v === 'object' ? JSON.stringify(v) : String(v ?? '--')
				]);
		}
	}

	function applyFilters() {
		loadEvents();
	}
</script>

<div class="flex h-full flex-col gap-4 overflow-y-auto p-6">
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
	<div class="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
		<!-- Top row: user filter, risk level, limit, apply -->
		<div class="flex items-end gap-3">
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
				<span class="text-xs text-text-secondary">Risk Level</span>
				<select
					bind:value={filterRiskLevel}
					class="w-32 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				>
					<option value="">All levels</option>
					{#each riskLevels.slice(1) as level}
						<option value={level}>{level}</option>
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

		<!-- Event type pills -->
		<div class="flex flex-wrap items-center gap-1.5">
			<span class="mr-1 text-xs text-text-secondary">Type:</span>
			<button
				type="button"
				onclick={() => { filterEventType = ''; applyFilters(); }}
				class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors
					{filterEventType === '' ? 'bg-accent text-white' : 'bg-surface-secondary text-text-secondary hover:bg-surface-hover hover:text-text-primary'}"
			>
				All
			</button>
			{#each eventTypes.slice(1) as type}
				<button
					type="button"
					onclick={() => { filterEventType = type; applyFilters(); }}
					class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors
						{filterEventType === type ? 'bg-accent text-white' : 'bg-surface-secondary text-text-secondary hover:bg-surface-hover hover:text-text-primary'}"
				>
					{formatEventType(type)}
				</button>
			{/each}
		</div>
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
							<th class="w-8 px-2 py-2"></th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Timestamp</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Event Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Risk</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">User</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Action</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Details</th>
						</tr>
					</thead>
					<tbody>
						{#each events as event, i}
							<tr
								class="border-b border-border cursor-pointer transition-colors hover:bg-surface-hover {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''} {expandedEventId === event.id ? 'bg-surface-hover' : ''}"
								onclick={() => toggleEventExpand(event.id)}
							>
								<td class="px-2 py-2 text-text-secondary">
									{#if expandedEventId === event.id}
										<ChevronDown size={14} />
									{:else}
										<ChevronRight size={14} />
									{/if}
								</td>
								<td class="whitespace-nowrap px-4 py-2">
									<span
										class="inline-flex items-center gap-1 text-xs text-text-secondary"
										title={formatFullTimestamp(event.timestamp)}
									>
										<Clock size={12} />
										{formatRelativeTime(event.timestamp)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {eventTypeColor(event.event_type)}"
									>
										{formatEventType(event.event_type)}
									</span>
								</td>
								<td class="px-4 py-2">
									{#if event.risk_level}
										<span class="inline-block rounded-full px-2 py-0.5 text-[11px] font-medium {riskLevelColor(event.risk_level)}">
											{event.risk_level}
										</span>
									{:else}
										<span class="text-xs text-text-secondary/40">--</span>
									{/if}
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{event.user_id}
								</td>
								<td class="px-4 py-2 text-text-primary">{event.action}</td>
								<td class="max-w-xs px-4 py-2 text-xs text-text-secondary" title={formatDetail(event.detail)}>
									{truncate(formatDetail(event.detail))}
								</td>
							</tr>

							<!-- Expanded detail row -->
							{#if expandedEventId === event.id}
								<tr transition:slide={{ duration: 200 }}>
									<td colspan="7" class="px-4 py-4 bg-surface-secondary/30 border-b border-border">
										{#if loadingDetail}
											<div class="flex items-center justify-center py-4">
												<Loader2 size={18} class="animate-spin text-text-secondary" />
											</div>
										{:else if expandedDetail}
											<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
												<!-- Left: structured detail -->
												<div>
													<h4 class="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wide">Event Details</h4>
													{#each formatDetailByType(expandedDetail) as [key, value]}
														<div class="flex gap-2 py-1">
															<span class="text-xs font-medium text-text-secondary w-28 shrink-0">{key}</span>
															<span class="text-xs text-text-primary break-all">{value}</span>
														</div>
													{/each}
												</div>

												<!-- Right: context -->
												<div>
													<h4 class="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wide">Context</h4>

													<!-- Risk level badge -->
													{#if expandedDetail.risk_level}
														<div class="flex items-center gap-2 py-1">
															<Shield size={12} class="shrink-0" />
															<span class="text-xs font-medium text-text-secondary w-24 shrink-0">Risk Level</span>
															<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium {riskLevelBadge(expandedDetail.risk_level)}">
																{expandedDetail.risk_level}
															</span>
														</div>
													{/if}

													<!-- Conversation link -->
													{#if expandedDetail.conversation_id}
														<div class="flex items-center gap-2 py-1">
															<ExternalLink size={12} class="shrink-0 text-text-secondary" />
															<span class="text-xs font-medium text-text-secondary w-24 shrink-0">Conversation</span>
															<a
																href="/conversations/{expandedDetail.conversation_id}"
																class="text-xs text-accent hover:underline"
																onclick={(e) => e.stopPropagation()}
															>
																{expandedDetail.conversation_id}
															</a>
														</div>
													{/if}

													<!-- System link -->
													{#if expandedDetail.system_id}
														<div class="flex items-center gap-2 py-1">
															<ExternalLink size={12} class="shrink-0 text-text-secondary" />
															<span class="text-xs font-medium text-text-secondary w-24 shrink-0">System</span>
															<a
																href="/admin/systems/{expandedDetail.system_id}"
																class="text-xs text-accent hover:underline"
																onclick={(e) => e.stopPropagation()}
															>
																{expandedDetail.system_id}
															</a>
														</div>
													{/if}

													<!-- Endpoint ID -->
													{#if expandedDetail.endpoint_id}
														<div class="flex items-center gap-2 py-1">
															<ExternalLink size={12} class="shrink-0 text-text-secondary" />
															<span class="text-xs font-medium text-text-secondary w-24 shrink-0">Endpoint</span>
															<span class="text-xs text-text-primary font-mono">{expandedDetail.endpoint_id}</span>
														</div>
													{/if}

													<!-- User ID -->
													<div class="flex items-center gap-2 py-1">
														<span class="text-xs font-medium text-text-secondary w-24 shrink-0 ml-[12px]">User</span>
														<span class="text-xs text-text-primary font-mono">{expandedDetail.user_id}</span>
													</div>
												</div>
											</div>

											<!-- Tool call details (if present) -->
											{#if expandedDetail.detail?.tool_name || expandedDetail.detail?.tool}
												<div class="mt-3 rounded-lg border border-border bg-surface p-3">
													<h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">Tool Call</h4>
													<div class="flex flex-wrap gap-x-6 gap-y-1 text-xs">
														<span><span class="font-medium text-text-secondary">Name:</span> <span class="font-mono text-text-primary">{expandedDetail.detail.tool_name ?? expandedDetail.detail.tool}</span></span>
														{#if expandedDetail.detail.duration_ms}
															<span><span class="font-medium text-text-secondary">Duration:</span> <span class="text-text-primary">{expandedDetail.detail.duration_ms}ms</span></span>
														{/if}
														{#if expandedDetail.risk_level}
															<span><span class="font-medium text-text-secondary">Risk:</span> <span class="inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium {riskLevelColor(expandedDetail.risk_level)}">{expandedDetail.risk_level}</span></span>
														{/if}
													</div>
													{#if expandedDetail.detail.arguments || expandedDetail.detail.parameters || expandedDetail.detail.params}
														<div class="mt-2">
															<span class="text-[11px] font-medium text-text-secondary">Parameters:</span>
															<pre class="mt-1 whitespace-pre-wrap break-all rounded-md border border-border bg-surface-secondary p-2 font-mono text-[11px] text-text-primary">{JSON.stringify(expandedDetail.detail.arguments ?? expandedDetail.detail.parameters ?? expandedDetail.detail.params, null, 2)}</pre>
														</div>
													{/if}
												</div>
											{/if}

											<!-- Bottom: raw JSON -->
											<details class="mt-3">
												<summary class="cursor-pointer text-xs text-text-secondary transition-colors hover:text-text-primary" onclick={(e: MouseEvent) => e.stopPropagation()}>
													Raw JSON
												</summary>
												<pre class="mt-2 whitespace-pre-wrap break-all rounded-md border border-border bg-surface p-3 font-mono text-[11px] text-text-primary">{JSON.stringify(expandedDetail.detail, null, 2)}</pre>
											</details>
										{/if}
									</td>
								</tr>
							{/if}
						{:else}
							<tr>
								<td colspan="7" class="px-4 py-8 text-center text-sm text-text-secondary">
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
