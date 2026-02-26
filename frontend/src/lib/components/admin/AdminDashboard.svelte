<!--
  AdminDashboard.svelte - Admin dashboard with stats, health, and recent events.

  Displays 4-column stat cards, operations/dev-tools actions, system health
  indicators, and a mini-table of recent audit events.

  Warm industrial design — ember accents, surface-elevated cards, micro-interactions.

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
		Activity,
		Trash2,
		RotateCcw,
		BookOpen,
		Wrench,
		FlaskConical,
		Clock,
		Coins,
		BarChart3,
		TrendingUp,
		ChevronLeft,
		ChevronRight
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import { currentUser } from '$lib/stores/user.js';
	import ChartWidget from '$lib/components/widgets/ChartWidget.svelte';

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

	interface ConversationAnalytics {
		messages_per_day: { date: string; count: number }[];
		avg_conversation_length: number;
		tool_usage: { tool_name: string; count: number }[];
		top_event_types: { event_type: string; count: number }[];
	}

	interface TokenUsageStats {
		total_input_tokens: number;
		total_output_tokens: number;
		estimated_cost_usd: number;
		period_days: number;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let stats = $state<SystemStats | null>(null);
	let health = $state<DetailedHealth | null>(null);
	let recentEvents = $state<AuditEventSummary[]>([]);
	let analytics = $state<ConversationAnalytics | null>(null);
	let tokenUsage = $state<TokenUsageStats | null>(null);
	let loading = $state(true);
	let error = $state('');

	// Action loading states
	let seedingData = $state(false);
	let testingLLM = $state(false);
	let clearingData = $state(false);
	let resettingSetup = $state(false);
	let refreshingIndex = $state(false);

	// Confirmation dialogs
	let showSeedConfirm = $state(false);
	let showClearConfirm = $state(false);
	let showResetConfirm = $state(false);

	// Year selector for heatmap
	let selectedYear = $state(new Date().getFullYear());
	let minYear = $derived.by(() => {
		const days = analytics?.messages_per_day;
		if (!days?.length) return selectedYear - 1;
		const years = days.map(d => parseInt(d.date.substring(0, 4)));
		return Math.min(...years, selectedYear - 1);
	});

	// Custom tooltip for heatmap
	let hoveredCell = $state<{date: string; count: number; x: number; y: number} | null>(null);

	// -----------------------------------------------------------------------
	// Activity heatmap (GitHub-style)
	// -----------------------------------------------------------------------

	interface HeatmapCell {
		date: string;
		count: number;
		level: 0 | 1 | 2 | 3 | 4;
		dayOfWeek: number; // 0 = Sun, 6 = Sat
		isFuture: boolean;
	}

	interface HeatmapWeek {
		cells: HeatmapCell[];
	}

	// Intentionally parsed without 'Z' suffix so the browser interprets as
	// local time — API returns calendar dates (YYYY-MM-DD), not UTC instants.
	function localDateStr(d: Date): string {
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		return `${y}-${m}-${day}`;
	}

	function formatHeatmapDate(dateStr: string): string {
		// No 'Z' — local-time interpretation (see localDateStr comment)
		const d = new Date(dateStr + 'T00:00:00');
		return d.toLocaleDateString('en-US', {
			weekday: 'short',
			month: 'short',
			day: 'numeric',
			year: 'numeric'
		});
	}

	const heatmapLevelClasses = [
		'bg-surface-secondary',     // level 0 — empty
		'bg-success/20',            // level 1
		'bg-success/40',            // level 2
		'bg-success/70',            // level 3
		'bg-success'                // level 4 — most active
	];

	let heatmapData = $derived.by(() => {
		const days = analytics?.messages_per_day;
		if (!days?.length && selectedYear === new Date().getFullYear()) return { weeks: [] as HeatmapWeek[], max: 0, monthHeaders: [] as {label: string; col: number; isFutureMonth: boolean}[] };

		const countMap = new Map<string, number>();
		if (days) {
			for (const d of days) countMap.set(d.date, d.count);
		}

		const now = new Date();

		// "today" at midnight for future-day comparison
		const today = new Date(now);
		today.setHours(0, 0, 0, 0);

		// Start: Jan 1 of selected year, padded back to Sunday
		const jan1 = new Date(selectedYear, 0, 1);
		const startDate = new Date(jan1);
		startDate.setDate(startDate.getDate() - startDate.getDay()); // back to Sunday

		// End: Dec 31 padded forward to Saturday (render full year grid)
		const endDate = new Date(selectedYear, 11, 31);
		if (endDate.getDay() !== 6) {
			endDate.setDate(endDate.getDate() + (6 - endDate.getDay()));
		}

		const maxCount = days?.length ? Math.max(...days.map(d => d.count), 1) : 1;

		const weeks: HeatmapWeek[] = [];
		const monthHeaders: {label: string; col: number; isFutureMonth: boolean}[] = [];
		let currentWeek: HeatmapCell[] = [];
		const cursor = new Date(startDate);
		let weekIndex = 0;
		let lastMonth = -1;
		const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

		// Pre-compute the current month/year for future-month detection
		const currentMonth = now.getMonth();
		const currentFullYear = now.getFullYear();

		while (cursor <= endDate) {
			const dateStr = localDateStr(cursor);
			const count = countMap.get(dateStr) ?? 0;
			const isFuture = cursor > today;
			const ratio = count / maxCount;
			let level: 0 | 1 | 2 | 3 | 4;
			if (count === 0) level = 0;
			else if (ratio <= 0.25) level = 1;
			else if (ratio <= 0.5) level = 2;
			else if (ratio <= 0.75) level = 3;
			else level = 4;

			// Track month headers — only for dates within the selected year
			// (skip December padding days from the previous year)
			const inYear = cursor.getFullYear() === selectedYear;
			if (inYear && cursor.getMonth() !== lastMonth) {
				// A month is "future" if it is entirely in the future
				// i.e. the selected year is in the future, or it's the current year
				// and this month is strictly after the current month
				const isFutureMonth = selectedYear > currentFullYear
					|| (selectedYear === currentFullYear && cursor.getMonth() > currentMonth);
				monthHeaders.push({ label: monthNames[cursor.getMonth()], col: weekIndex, isFutureMonth });
				lastMonth = cursor.getMonth();
			}

			currentWeek.push({ date: dateStr, count, level, dayOfWeek: cursor.getDay(), isFuture });

			if (cursor.getDay() === 6) {
				weeks.push({ cells: currentWeek });
				currentWeek = [];
				weekIndex++;
			}

			cursor.setDate(cursor.getDate() + 1);
		}

		if (currentWeek.length > 0) {
			weeks.push({ cells: currentWeek });
		}

		return { weeks, max: maxCount, monthHeaders };
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	let loadSeq = 0;

	async function loadDashboard() {
		const seq = ++loadSeq;
		loading = true;
		error = '';
		try {
			const now = new Date();
			const isCurrentYear = selectedYear === now.getFullYear();
			const jan1 = new Date(selectedYear, 0, 1);
			const endDate = isCurrentYear ? now : new Date(selectedYear, 11, 31);
			const daysToFetch = Math.ceil((endDate.getTime() - jan1.getTime()) / 86400000) + 1;
			const [statsData, healthData, eventsData, analyticsData, tokenData] = await Promise.all([
				apiJson<SystemStats>('/admin/dashboard/stats'),
				apiJson<DetailedHealth>('/admin/dashboard/health'),
				apiJson<AuditEventSummary[]>('/admin/dashboard/recent-events'),
				apiJson<ConversationAnalytics>(`/admin/dashboard/analytics?days=${daysToFetch}`).catch(() => null),
				apiJson<TokenUsageStats>('/admin/dashboard/token-usage').catch(() => null)
			]);
			if (seq !== loadSeq) return;
			stats = statsData;
			health = healthData;
			recentEvents = eventsData;
			analytics = analyticsData;
			tokenUsage = tokenData;
		} catch (e) {
			if (seq !== loadSeq) return;
			error = e instanceof Error ? e.message : 'Failed to load dashboard data';
		} finally {
			if (seq === loadSeq) loading = false;
		}
	}

	// Initial load
	$effect(() => {
		loadDashboard();
	});

	// -----------------------------------------------------------------------
	// Operations actions
	// -----------------------------------------------------------------------

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

	async function refreshKnowledgeIndex() {
		refreshingIndex = true;
		error = '';
		try {
			await apiFetch('/knowledge/reindex', { method: 'POST', body: JSON.stringify({}) });
			await loadDashboard();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Knowledge reindex failed';
		} finally {
			refreshingIndex = false;
		}
	}

	// -----------------------------------------------------------------------
	// Development tools actions
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

	function confirmSeed() {
		showSeedConfirm = false;
		seedData();
	}

	function confirmClear() {
		showClearConfirm = false;
		clearDemoData();
	}

	function confirmReset() {
		showResetConfirm = false;
		resetSetup();
	}

	async function clearDemoData() {
		clearingData = true;
		error = '';
		try {
			await apiFetch('/setup/clear', { method: 'POST', body: JSON.stringify({}) });
			await loadDashboard();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Clear demo data failed';
		} finally {
			clearingData = false;
		}
	}

	async function resetSetup() {
		resettingSetup = true;
		error = '';
		try {
			await apiFetch('/setup/reset', { method: 'POST', body: JSON.stringify({}) });
			await loadDashboard();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Reset setup failed';
		} finally {
			resettingSetup = false;
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

	function formatTimestamp(ts: string | null): string {
		if (!ts) return '--';
		const date = new Date(ts);
		if (isNaN(date.getTime())) return '--';
		return date.toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit',
			hour12: true
		});
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

	function healthDotClass(status: string): string {
		const base = 'inline-block h-2.5 w-2.5 rounded-full';
		switch (status) {
			case 'healthy':
				return `${base} bg-success animate-pulse-health`;
			case 'degraded':
				return `${base} bg-warning`;
			case 'unhealthy':
				return `${base} bg-danger`;
			default:
				return `${base} bg-text-secondary`;
		}
	}

	function formatTokenCount(n: number): string {
		if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
		if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
		return String(n);
	}

	// -----------------------------------------------------------------------
	// Year navigation & tooltip helpers
	// -----------------------------------------------------------------------

	function changeYear(delta: number) {
		const newYear = selectedYear + delta;
		const currentYear = new Date().getFullYear();
		if (newYear > currentYear || newYear < minYear) return;
		selectedYear = newYear;
		reloadAnalytics();
	}

	async function reloadAnalytics() {
		const now = new Date();
		const isCurrentYear = selectedYear === now.getFullYear();
		const jan1 = new Date(selectedYear, 0, 1);
		// API counts backwards from today, so request enough days to reach Jan 1 of selectedYear
		const daysFromToday = Math.ceil((now.getTime() - jan1.getTime()) / 86400000) + 1;
		try {
			const data = await apiJson<ConversationAnalytics>(`/admin/dashboard/analytics?days=${daysFromToday}`);
			if (data && !isCurrentYear) {
				// Filter to only the selected calendar year
				const yearPrefix = String(selectedYear);
				data.messages_per_day = data.messages_per_day.filter(d => d.date.startsWith(yearPrefix));
			}
			analytics = data;
		} catch {
			// Analytics are optional
		}
	}

	function showTooltip(cell: HeatmapCell, e: MouseEvent) {
		if (cell.isFuture) return;
		const TOOLTIP_W = 180;
		const x = e.clientX + 12 + TOOLTIP_W > window.innerWidth
			? e.clientX - TOOLTIP_W - 4
			: e.clientX + 12;
		hoveredCell = { date: cell.date, count: cell.count, x, y: e.clientY - 10 };
	}

	function hideTooltip() {
		hoveredCell = null;
	}
</script>

<style>
	@keyframes pulse-health {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}

	:global(.animate-pulse-health) {
		animation: pulse-health 2s ease-in-out infinite;
	}
</style>

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
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
		>
			<RefreshCw size={14} />
			Refresh
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
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
			<div
				class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
			>
				<div
					class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-accent/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
				></div>
				<div class="relative flex items-center gap-3">
					<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10">
						<MessageSquare size={20} class="text-accent" />
					</div>
					<div>
						<p class="text-3xl font-bold text-text-primary">
							{stats?.conversation_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Conversations</p>
					</div>
				</div>
			</div>

			<div
				class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
			>
				<div
					class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-success/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
				></div>
				<div class="relative flex items-center gap-3">
					<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-success/10">
						<Users size={20} class="text-success" />
					</div>
					<div>
						<p class="text-3xl font-bold text-text-primary">
							{stats?.active_user_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Active Users</p>
					</div>
				</div>
			</div>

			<div
				class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
			>
				<div
					class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-ember/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
				></div>
				<div class="relative flex items-center gap-3">
					<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-ember/10">
						<Database size={20} class="text-ember" />
					</div>
					<div>
						<p class="text-3xl font-bold text-text-primary">
							{stats?.system_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Systems</p>
					</div>
				</div>
			</div>

			<div
				class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
			>
				<div
					class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-accent/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
				></div>
				<div class="relative flex items-center gap-3">
					<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10">
						<FileText size={20} class="text-accent" />
					</div>
					<div>
						<p class="text-3xl font-bold text-text-primary">
							{stats?.knowledge_doc_count ?? 0}
						</p>
						<p class="text-xs text-text-secondary">Knowledge Docs</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Analytics stat cards (second row) -->
		{#if tokenUsage || analytics}
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{#if tokenUsage}
					<div
						class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
					>
						<div
							class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-ember/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
						></div>
						<div class="relative flex items-center gap-3">
							<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-ember/10">
								<BarChart3 size={20} class="text-ember" />
							</div>
							<div>
								<p class="text-3xl font-bold text-text-primary">
									{formatTokenCount(tokenUsage.total_input_tokens + tokenUsage.total_output_tokens)}
								</p>
								<p class="text-xs text-text-secondary">Total Tokens</p>
							</div>
						</div>
					</div>

					<div
						class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
					>
						<div
							class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-warning/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
						></div>
						<div class="relative flex items-center gap-3">
							<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-warning/10">
								<Coins size={20} class="text-warning" />
							</div>
							<div>
								<p class="text-3xl font-bold text-text-primary">
									${tokenUsage.estimated_cost_usd.toFixed(2)}
								</p>
								<p class="text-xs text-text-secondary">Estimated Cost</p>
							</div>
						</div>
					</div>
				{/if}

				{#if analytics}
					<div
						class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
					>
						<div
							class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-success/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
						></div>
						<div class="relative flex items-center gap-3">
							<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-success/10">
								<TrendingUp size={20} class="text-success" />
							</div>
							<div>
								<p class="text-3xl font-bold text-text-primary">
									{analytics.messages_per_day?.length
										? analytics.messages_per_day[analytics.messages_per_day.length - 1].count
										: 0}
								</p>
								<p class="text-xs text-text-secondary">Messages Today</p>
							</div>
						</div>
					</div>

					<div
						class="group relative rounded-xl border border-border bg-surface-elevated p-5 shadow-sm transition-shadow hover:shadow-md"
					>
						<div
							class="pointer-events-none absolute inset-0 rounded-xl border border-transparent bg-gradient-to-br from-accent/20 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100"
						></div>
						<div class="relative flex items-center gap-3">
							<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10">
								<MessageSquare size={20} class="text-accent" />
							</div>
							<div>
								<p class="text-3xl font-bold text-text-primary">
									{analytics.avg_conversation_length?.toFixed(1) ?? '--'}
								</p>
								<p class="text-xs text-text-secondary">Avg Conv Length</p>
							</div>
						</div>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Charts section -->
		{#if analytics || tokenUsage}
			<!-- Conversation Activity — GitHub-style heatmap -->
			{#if heatmapData.weeks.length > 0}
				<div class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm">
					<!-- Header with year selector -->
					<div class="mb-4 flex items-center justify-between">
						<h2 class="text-sm font-semibold text-text-primary">Conversation Activity</h2>
						<div class="flex items-center gap-1">
							<button type="button" onclick={() => changeYear(-1)}
								class="rounded p-1 text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:opacity-30"
								disabled={selectedYear <= minYear}>
								<ChevronLeft size={14} />
							</button>
							<span class="min-w-[3rem] text-center text-xs font-medium text-text-primary">{selectedYear}</span>
							<button type="button" onclick={() => changeYear(1)}
								class="rounded p-1 text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:opacity-30"
								disabled={selectedYear >= new Date().getFullYear()}>
								<ChevronRight size={14} />
							</button>
						</div>
					</div>

					<div class="relative">
						<!-- Month headers -->
						<div class="mb-1 flex pl-7" style="gap: 2px;">
							{#each heatmapData.monthHeaders as header, i}
								{@const nextCol = i < heatmapData.monthHeaders.length - 1 ? heatmapData.monthHeaders[i + 1].col : heatmapData.weeks.length}
								{@const span = nextCol - header.col}
								{#if i === 0 && header.col > 0}
									<div style="flex: {header.col}"></div>
								{/if}
								<div style="flex: {span}"
									 class="text-[10px] leading-none text-text-secondary truncate {header.isFutureMonth ? 'opacity-20' : ''}">
									{header.label}
								</div>
							{/each}
						</div>

						<div class="flex items-stretch gap-1.5">
							<!-- Day-of-week labels -->
							<div class="flex shrink-0 flex-col justify-between">
								<span class="text-[10px] leading-[11px] text-text-secondary">&nbsp;</span>
								<span class="text-[10px] leading-[11px] text-text-secondary">Mon</span>
								<span class="text-[10px] leading-[11px] text-text-secondary">&nbsp;</span>
								<span class="text-[10px] leading-[11px] text-text-secondary">Wed</span>
								<span class="text-[10px] leading-[11px] text-text-secondary">&nbsp;</span>
								<span class="text-[10px] leading-[11px] text-text-secondary">Fri</span>
								<span class="text-[10px] leading-[11px] text-text-secondary">&nbsp;</span>
							</div>

							<!-- Heatmap grid — flex-1 stretches to fill container -->
							<div class="flex flex-1 min-w-0 gap-[2px]">
								{#each heatmapData.weeks as week, wi}
									<div class="flex flex-1 min-w-0 flex-col gap-[2px]">
										{#each week.cells as cell}
											<div
												class="aspect-square w-full rounded-[2px] {heatmapLevelClasses[cell.level]} {cell.isFuture ? 'opacity-20' : ''}"
												role="presentation"
												onmouseenter={(e) => showTooltip(cell, e)}
												onmouseleave={hideTooltip}
											></div>
										{/each}
									</div>
								{/each}
							</div>
						</div>

						<!-- Custom tooltip -->
						{#if hoveredCell}
							<div
								class="pointer-events-none fixed z-50 rounded-lg border border-border bg-surface-elevated px-3 py-2 text-xs shadow-lg"
								style="left: {hoveredCell.x}px; top: {hoveredCell.y - 40}px;"
							>
								<div class="font-medium text-text-primary">{formatHeatmapDate(hoveredCell.date)}</div>
								<div class="text-text-secondary">{hoveredCell.count} message{hoveredCell.count !== 1 ? 's' : ''}</div>
							</div>
						{/if}
					</div>

					<!-- Legend -->
					<div class="mt-3 flex items-center justify-end gap-1.5">
						<span class="text-[10px] text-text-secondary">Less</span>
						{#each heatmapLevelClasses as cls}
							<div class="h-[11px] w-[11px] rounded-[2px] {cls}"></div>
						{/each}
						<span class="text-[10px] text-text-secondary">More</span>
					</div>
				</div>
			{/if}

			<!-- Tool Usage + Token Usage side by side -->
			<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
				{#if analytics?.tool_usage?.length}
					<ChartWidget
						chartType="bar"
						title="Tool Usage"
						labels={analytics.tool_usage.map(t => t.tool_name)}
						datasets={[{
							label: 'Calls',
							data: analytics.tool_usage.map(t => t.count)
						}]}
						options={{ indexAxis: 'y', plugins: { legend: { display: false } } }}
					/>
				{/if}

				{#if tokenUsage && (tokenUsage.total_input_tokens > 0 || tokenUsage.total_output_tokens > 0)}
					<ChartWidget
						chartType="doughnut"
						title="Token Usage"
						labels={['Input Tokens', 'Output Tokens']}
						datasets={[{
							label: 'Tokens',
							data: [tokenUsage.total_input_tokens, tokenUsage.total_output_tokens]
						}]}
					/>
				{/if}
			</div>
		{/if}

		<!-- Operations (always visible) -->
		<div class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm">
			<div class="mb-4 flex items-center gap-2">
				<Wrench size={16} class="text-text-secondary" />
				<h2 class="text-sm font-semibold text-text-primary">Operations</h2>
			</div>
			<div class="flex flex-wrap gap-2">
				<button
					type="button"
					onclick={testLLMConnection}
					disabled={testingLLM}
					class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-all hover:bg-surface-hover disabled:opacity-50"
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
					class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-all hover:bg-surface-hover"
				>
					<AlertTriangle size={14} />
					View Audit Log
				</a>

				<button
					type="button"
					onclick={refreshKnowledgeIndex}
					disabled={refreshingIndex}
					class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-all hover:bg-surface-hover disabled:opacity-50"
				>
					{#if refreshingIndex}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<BookOpen size={14} />
					{/if}
					Refresh Knowledge Index
				</button>
			</div>
		</div>

		<!-- Development Tools (only visible in devMode) -->
		{#if $currentUser?.devMode}
			<div class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm">
				<div class="mb-4 flex items-center gap-2">
					<FlaskConical size={16} class="text-ember" />
					<h2 class="text-sm font-semibold text-text-primary">Development Tools</h2>
					<span
						class="inline-flex items-center rounded-md bg-ember/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ember"
					>
						Dev
					</span>
				</div>
				<div class="flex flex-wrap gap-2">
					<button
						type="button"
						onclick={() => (showSeedConfirm = true)}
						disabled={seedingData}
						class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition-all hover:bg-accent-hover disabled:opacity-50"
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
						onclick={() => (showClearConfirm = true)}
						disabled={clearingData}
						class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-danger/30 px-3 py-1.5 text-sm font-medium text-danger transition-all hover:bg-danger/5 disabled:opacity-50"
					>
						{#if clearingData}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Trash2 size={14} />
						{/if}
						Clear Demo Data
					</button>

					<button
						type="button"
						onclick={() => (showResetConfirm = true)}
						disabled={resettingSetup}
						class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-danger/30 px-3 py-1.5 text-sm font-medium text-danger transition-all hover:bg-danger/5 disabled:opacity-50"
					>
						{#if resettingSetup}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<RotateCcw size={14} />
						{/if}
						Reset Setup
					</button>
				</div>
			</div>
		{/if}

		<!-- System health -->
		{#if health}
			<div class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm">
				<div class="mb-4 flex items-center justify-between">
					<h2 class="text-sm font-semibold text-text-primary">System Health</h2>
					<div class="flex items-center gap-3">
						<span
							class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium {healthBg(health.overall)} {healthColor(health.overall)}"
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
							class="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5"
						>
							<div class="flex items-center gap-2">
								<Activity size={14} class={healthColor(component.status)} />
								<span class="text-sm font-medium text-text-primary">{component.name}</span>
							</div>
							<div class="flex items-center gap-2">
								{#if component.latency_ms !== null}
									<span class="text-xs text-text-secondary">
										{component.latency_ms}ms
									</span>
								{/if}
								<span class={healthDotClass(component.status)} aria-label="{component.status} status"></span>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Recent audit events -->
		<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
			<div class="border-b border-border px-5 py-3.5">
				<h2 class="text-sm font-semibold text-text-primary">Recent Activity</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary/50">
							<th class="px-5 py-2.5 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-5 py-2.5 text-xs font-medium text-text-secondary">User</th>
							<th class="px-5 py-2.5 text-xs font-medium text-text-secondary">Action</th>
							<th class="px-5 py-2.5 text-xs font-medium text-text-secondary">Time</th>
						</tr>
					</thead>
					<tbody>
						{#each recentEvents as event}
							<tr class="border-b border-border last:border-b-0 even:bg-surface-secondary/30">
								<td class="px-5 py-2.5">
									<span
										class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										{event.event_type}
									</span>
								</td>
								<td class="px-5 py-2.5 text-text-secondary">{event.user_id}</td>
								<td class="px-5 py-2.5 text-text-primary">{event.action}</td>
								<td class="px-5 py-2.5 text-text-secondary">
									<span class="inline-flex items-center gap-1">
										<Clock size={12} class="text-text-secondary/60" />
										{formatTimestamp(event.created_at)}
									</span>
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="4" class="px-5 py-8 text-center text-sm text-text-secondary">
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

<!-- Seed data confirmation dialog -->
{#if showSeedConfirm}
	<div
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		aria-labelledby="seed-dialog-title"
		aria-describedby="seed-dialog-desc"
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		onkeydown={(e) => { if (e.key === 'Escape') showSeedConfirm = false; }}
	>
		<div class="w-full max-w-md rounded-xl border border-border bg-surface-elevated p-6 shadow-xl">
			<h3 id="seed-dialog-title" class="text-base font-semibold text-text-primary">Load Demo Data</h3>
			<p id="seed-dialog-desc" class="mt-2 text-sm text-text-secondary">
				This loads sample banking systems and knowledge documents for demo purposes. Continue?
			</p>
			<div class="mt-5 flex justify-end gap-3">
				<button
					type="button"
					onclick={() => (showSeedConfirm = false)}
					class="btn-hover rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={confirmSeed}
					class="btn-hover rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-all hover:bg-accent-hover"
				>
					Continue
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Clear demo data confirmation dialog -->
{#if showClearConfirm}
	<div
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		aria-labelledby="clear-dialog-title"
		aria-describedby="clear-dialog-desc"
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		onkeydown={(e) => { if (e.key === 'Escape') showClearConfirm = false; }}
	>
		<div class="w-full max-w-md rounded-xl border border-border bg-surface-elevated p-6 shadow-xl">
			<h3 id="clear-dialog-title" class="text-base font-semibold text-danger">Clear Demo Data</h3>
			<p id="clear-dialog-desc" class="mt-2 text-sm text-text-secondary">
				This will remove all demo data including sample systems and knowledge documents. This action cannot be undone.
			</p>
			<div class="mt-5 flex justify-end gap-3">
				<button
					type="button"
					onclick={() => (showClearConfirm = false)}
					class="btn-hover rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={confirmClear}
					class="btn-hover rounded-lg bg-danger px-4 py-2 text-sm font-medium text-white transition-all hover:bg-danger/90"
				>
					Clear Data
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Reset setup confirmation dialog -->
{#if showResetConfirm}
	<div
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		aria-labelledby="reset-dialog-title"
		aria-describedby="reset-dialog-desc"
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		onkeydown={(e) => { if (e.key === 'Escape') showResetConfirm = false; }}
	>
		<div class="w-full max-w-md rounded-xl border border-border bg-surface-elevated p-6 shadow-xl">
			<h3 id="reset-dialog-title" class="text-base font-semibold text-danger">Reset Setup</h3>
			<p id="reset-dialog-desc" class="mt-2 text-sm text-text-secondary">
				This will reset the setup wizard and clear all configuration. You will need to complete setup again. This action cannot be undone.
			</p>
			<div class="mt-5 flex justify-end gap-3">
				<button
					type="button"
					onclick={() => (showResetConfirm = false)}
					class="btn-hover rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={confirmReset}
					class="btn-hover rounded-lg bg-danger px-4 py-2 text-sm font-medium text-white transition-all hover:bg-danger/90"
				>
					Reset
				</button>
			</div>
		</div>
	</div>
{/if}
