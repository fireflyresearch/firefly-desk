<!--
  AdminDashboard.svelte - Admin dashboard with stats, health, and recent events.

  Displays 4-column stat cards, quick actions, system health indicators,
  and a mini-table of recent audit events.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		MessageSquare,
		Users,
		Database,
		FileText,
		Loader2,
		RefreshCw,
		Zap,
		AlertTriangle,
		CheckCircle,
		XCircle,
		Activity
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface SystemStats {
		conversation_count: number;
		message_count: number;
		active_user_count: number;
		system_count: number;
		knowledge_doc_count: number;
		audit_event_count: number;
		llm_provider_count: number;
	}

	interface ComponentHealth {
		name: string;
		status: string;
		detail: string | null;
		latency_ms: number | null;
	}

	interface DetailedHealth {
		overall: string;
		uptime_seconds: number;
		started_at: string | null;
		components: ComponentHealth[];
	}

	interface AuditEventSummary {
		event_type: string;
		user_id: string;
		action: string;
		detail: Record<string, unknown>;
		created_at: string | null;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let stats = $state<SystemStats | null>(null);
	let health = $state<DetailedHealth | null>(null);
	let recentEvents = $state<AuditEventSummary[]>([]);
	let loading = $state(true);
	let error = $state('');
	let seedingData = $state(false);
	let testingLLM = $state(false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadDashboard() {
		loading = true;
		error = '';
		try {
			const [statsData, healthData, eventsData] = await Promise.all([
				apiJson<SystemStats>('/admin/dashboard/stats'),
				apiJson<DetailedHealth>('/admin/dashboard/health'),
				apiJson<AuditEventSummary[]>('/admin/dashboard/recent-events')
			]);
			stats = statsData;
			health = healthData;
			recentEvents = eventsData;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load dashboard data';
		} finally {
			loading = false;
		}
	}

	// Initial load
	$effect(() => {
		loadDashboard();
	});

	// -----------------------------------------------------------------------
	// Quick actions
	// -----------------------------------------------------------------------

	async function seedData() {
		seedingData = true;
		error = '';
		try {
			await apiFetch('/setup/seed', { method: 'POST', body: JSON.stringify({}) });
			await loadDashboard();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Seed failed';
		} finally {
			seedingData = false;
		}
	}

	async function testLLMConnection() {
		testingLLM = true;
		error = '';
		try {
			const healthData = await apiJson<DetailedHealth>('/admin/dashboard/health');
			health = healthData;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Health check failed';
		} finally {
			testingLLM = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function formatUptime(seconds: number): string {
		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		const mins = Math.floor((seconds % 3600) / 60);
		if (days > 0) return `${days}d ${hours}h ${mins}m`;
		if (hours > 0) return `${hours}h ${mins}m`;
		return `${mins}m`;
	}

	function healthColor(status: string): string {
		switch (status) {
			case 'healthy':
				return 'text-success';
			case 'degraded':
				return 'text-warning';
			case 'unhealthy':
				return 'text-danger';
			default:
				return 'text-text-secondary';
		}
	}

	function healthBg(status: string): string {
		switch (status) {
			case 'healthy':
				return 'bg-success/10';
			case 'degraded':
				return 'bg-warning/10';
			case 'unhealthy':
				return 'bg-danger/10';
			default:
				return 'bg-surface-secondary';
		}
	}
</script>

<div class="flex h-full flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Dashboard</h1>
			<p class="text-sm text-text-secondary">System overview and health status</p>
		</div>
		<button
			type="button"
			onclick={loadDashboard}
			class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			<RefreshCw size={14} />
			Refresh
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<!-- Stat cards -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="flex items-center gap-3">
					<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
						<MessageSquare size={20} class="text-accent" />
					</div>
					<div>
						<p class="text-2xl font-semibold text-text-primary">
							{stats?.conversation_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Conversations</p>
					</div>
				</div>
			</div>

			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="flex items-center gap-3">
					<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-success/10">
						<Users size={20} class="text-success" />
					</div>
					<div>
						<p class="text-2xl font-semibold text-text-primary">
							{stats?.active_user_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Active Users</p>
					</div>
				</div>
			</div>

			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="flex items-center gap-3">
					<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10">
						<Database size={20} class="text-warning" />
					</div>
					<div>
						<p class="text-2xl font-semibold text-text-primary">
							{stats?.system_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Systems</p>
					</div>
				</div>
			</div>

			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="flex items-center gap-3">
					<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
						<FileText size={20} class="text-accent" />
					</div>
					<div>
						<p class="text-2xl font-semibold text-text-primary">
							{stats?.knowledge_doc_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Knowledge Docs</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Quick actions -->
		<div class="rounded-lg border border-border bg-surface p-4">
			<h2 class="mb-3 text-sm font-semibold text-text-primary">Quick Actions</h2>
			<div class="flex flex-wrap gap-2">
				<button
					type="button"
					onclick={seedData}
					disabled={seedingData}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if seedingData}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Database size={14} />
					{/if}
					Seed Data
				</button>

				<button
					type="button"
					onclick={testLLMConnection}
					disabled={testingLLM}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
				>
					{#if testingLLM}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Zap size={14} />
					{/if}
					Test LLM Connection
				</button>

				<a
					href="/admin/audit"
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover"
				>
					<AlertTriangle size={14} />
					View Audit Log
				</a>
			</div>
		</div>

		<!-- System health -->
		{#if health}
			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-sm font-semibold text-text-primary">System Health</h2>
					<div class="flex items-center gap-2">
						<span
							class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium {healthBg(health.overall)} {healthColor(health.overall)}"
						>
							{#if health.overall === 'healthy'}
								<CheckCircle size={12} />
							{:else if health.overall === 'degraded'}
								<AlertTriangle size={12} />
							{:else}
								<XCircle size={12} />
							{/if}
							{health.overall}
						</span>
						{#if health.uptime_seconds > 0}
							<span class="text-xs text-text-secondary">
								Uptime: {formatUptime(health.uptime_seconds)}
							</span>
						{/if}
					</div>
				</div>

				<div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
					{#each health.components as component}
						<div
							class="flex items-center justify-between rounded-md border border-border px-3 py-2"
						>
							<div class="flex items-center gap-2">
								<Activity size={14} class={healthColor(component.status)} />
								<span class="text-sm text-text-primary">{component.name}</span>
							</div>
							<div class="flex items-center gap-2">
								{#if component.latency_ms}
									<span class="text-xs text-text-secondary">
										{component.latency_ms}ms
									</span>
								{/if}
								<span
									class="inline-block h-2 w-2 rounded-full {component.status === 'healthy'
										? 'bg-success'
										: component.status === 'degraded'
											? 'bg-warning'
											: 'bg-danger'}"
								></span>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Recent audit events -->
		<div class="rounded-lg border border-border bg-surface">
			<div class="border-b border-border px-4 py-3">
				<h2 class="text-sm font-semibold text-text-primary">Recent Activity</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">User</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Action</th>
						</tr>
					</thead>
					<tbody>
						{#each recentEvents as event}
							<tr class="border-b border-border last:border-b-0">
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										{event.event_type}
									</span>
								</td>
								<td class="px-4 py-2 text-text-secondary">{event.user_id}</td>
								<td class="px-4 py-2 text-text-primary">{event.action}</td>
							</tr>
						{:else}
							<tr>
								<td colspan="3" class="px-4 py-8 text-center text-sm text-text-secondary">
									No recent activity.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
