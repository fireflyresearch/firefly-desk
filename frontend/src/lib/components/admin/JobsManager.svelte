<!--
  JobsManager.svelte - Background jobs management table with filters.

  Displays a filterable, auto-refreshable table of background jobs with
  status badges, progress bars, duration, expandable detail rows, and
  pagination matching the KnowledgeBaseManager pattern.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Activity,
		Loader2,
		CheckCircle,
		AlertCircle,
		Clock,
		XCircle,
		RefreshCw,
		ChevronDown,
		ChevronRight
	} from 'lucide-svelte';
	import { slide, fade } from 'svelte/transition';
	import { fetchJobs, fetchJob, type Job, type JobFilters } from '$lib/services/jobs.js';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let jobs = $state<Job[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');

	// Filters
	let filterType = $state('');
	let filterStatus = $state('');

	// Pagination
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Auto-refresh
	let autoRefresh = $state(false);
	let refreshInterval = $state<ReturnType<typeof setInterval> | null>(null);

	// Expanded row
	let expandedJobId = $state<string | null>(null);
	let expandedJob = $state<Job | null>(null);
	let loadingDetail = $state(false);

	const jobTypes = [
		{ value: '', label: 'All types' },
		{ value: 'indexing', label: 'Indexing' },
		{ value: 'source_sync', label: 'Source Sync' },
		{ value: 'process_discovery', label: 'Process Discovery' },
		{ value: 'system_discovery', label: 'System Discovery' },
		{ value: 'kg_recompute', label: 'KG Recompute' },
		{ value: 'kg_extract_single', label: 'KG Extract Single' }
	];

	const statusOptions = [
		{ value: '', label: 'All statuses' },
		{ value: 'pending', label: 'Pending' },
		{ value: 'running', label: 'Running' },
		{ value: 'completed', label: 'Completed' },
		{ value: 'failed', label: 'Failed' },
		{ value: 'cancelled', label: 'Cancelled' }
	];

	// -----------------------------------------------------------------------
	// Derived (pagination)
	// -----------------------------------------------------------------------

	let filteredJobs = $derived.by(() => {
		return jobs.filter((j) => {
			const matchesType = !filterType || j.job_type === filterType;
			const matchesStatus = !filterStatus || j.status === filterStatus;
			return matchesType && matchesStatus;
		});
	});

	let totalPages = $derived(Math.max(1, Math.ceil(filteredJobs.length / pageSize)));
	let paginatedJobs = $derived(
		filteredJobs.slice((currentPage - 1) * pageSize, currentPage * pageSize)
	);

	// Reset page when filters change
	$effect(() => {
		void filterType;
		void filterStatus;
		currentPage = 1;
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadJobs(isRefresh = false) {
		if (isRefresh) {
			refreshing = true;
		} else {
			loading = true;
		}
		error = '';
		try {
			const filters: JobFilters = {};
			jobs = await fetchJobs(filters);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load jobs';
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	// Initial load
	$effect(() => {
		loadJobs();
	});

	// Auto-refresh management
	$effect(() => {
		if (autoRefresh) {
			refreshInterval = setInterval(() => {
				loadJobs(true);
			}, 5_000);
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

	function statusBadgeClass(status: Job['status']): string {
		switch (status) {
			case 'pending':
				return 'border border-border bg-surface-secondary text-text-secondary';
			case 'running':
				return 'border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400';
			case 'completed':
				return 'border border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400';
			case 'failed':
				return 'border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400';
			case 'cancelled':
				return 'border border-border bg-surface-secondary text-text-secondary';
			default:
				return 'border border-border bg-surface-secondary text-text-secondary';
		}
	}

	function statusLabel(status: Job['status']): string {
		return status.charAt(0).toUpperCase() + status.slice(1);
	}

	function formatJobType(type: string): string {
		return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	function formatRelativeTime(iso: string | null): string {
		if (!iso) return '--';
		const d = new Date(iso);
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

	function formatFullTimestamp(iso: string | null): string {
		if (!iso) return '--';
		const d = new Date(iso);
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

	function computeDuration(job: Job): string {
		if (!job.created_at) return '--';
		const start = new Date(job.created_at).getTime();

		if (job.status === 'running') {
			return 'running...';
		}

		if (!job.completed_at) return '--';
		const end = new Date(job.completed_at).getTime();
		const diffMs = end - start;

		if (diffMs < 1000) return `${diffMs}ms`;
		const diffSec = Math.floor(diffMs / 1000);
		if (diffSec < 60) return `${diffSec}s`;
		const diffMin = Math.floor(diffSec / 60);
		const remSec = diffSec % 60;
		if (diffMin < 60) return `${diffMin}m ${remSec}s`;
		const diffHr = Math.floor(diffMin / 60);
		const remMin = diffMin % 60;
		return `${diffHr}h ${remMin}m`;
	}

	// -----------------------------------------------------------------------
	// Expand / collapse
	// -----------------------------------------------------------------------

	async function toggleJobExpand(jobId: string) {
		if (expandedJobId === jobId) {
			expandedJobId = null;
			expandedJob = null;
			return;
		}
		expandedJobId = jobId;
		loadingDetail = true;
		try {
			expandedJob = await fetchJob(jobId);
		} catch {
			expandedJob = jobs.find((j) => j.id === jobId) ?? null;
		} finally {
			loadingDetail = false;
		}
	}
</script>

<div class="flex h-full flex-col gap-4 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Background Jobs</h1>
			<p class="text-sm text-text-secondary">Monitor and inspect background tasks across the system</p>
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
				onclick={() => loadJobs(true)}
				disabled={refreshing}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-50"
			>
				<RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
				Refresh
			</button>
		</div>
	</div>

	<!-- Filter bar -->
	<div class="flex items-center gap-3">
		<select
			bind:value={filterType}
			class="h-8 rounded-lg border border-border bg-surface px-2.5 text-sm text-text-primary outline-none focus:border-accent"
		>
			{#each jobTypes as jt}
				<option value={jt.value}>{jt.label}</option>
			{/each}
		</select>

		<select
			bind:value={filterStatus}
			class="h-8 rounded-lg border border-border bg-surface px-2.5 text-sm text-text-primary outline-none focus:border-accent"
		>
			{#each statusOptions as so}
				<option value={so.value}>{so.label}</option>
			{/each}
		</select>

		{#if filterType || filterStatus}
			<button
				type="button"
				onclick={() => { filterType = ''; filterStatus = ''; }}
				class="text-xs text-text-secondary transition-colors hover:text-text-primary"
			>
				Clear filters
			</button>
		{/if}

		<span class="ml-auto text-xs text-text-secondary">
			{filteredJobs.length} job{filteredJobs.length !== 1 ? 's' : ''}
		</span>
	</div>

	<!-- Error -->
	{#if error}
		<div class="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-500">
			<AlertCircle size={16} />
			{error}
		</div>
	{/if}

	<!-- Table -->
	{#if loading && jobs.length === 0}
		<div class="flex flex-1 items-center justify-center">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if filteredJobs.length === 0}
		<!-- Empty state -->
		<div class="flex flex-1 flex-col items-center justify-center gap-3 text-text-secondary">
			<Activity size={40} strokeWidth={1} class="opacity-30" />
			<p class="text-sm">No jobs match the current filters</p>
			{#if filterType || filterStatus}
				<button
					type="button"
					onclick={() => { filterType = ''; filterStatus = ''; }}
					class="text-xs text-accent transition-colors hover:underline"
				>
					Clear filters
				</button>
			{/if}
		</div>
	{:else}
		<div class="relative overflow-hidden rounded-lg border border-border">
			<!-- Refresh overlay indicator -->
			{#if refreshing}
				<div
					transition:fade={{ duration: 150 }}
					class="pointer-events-none absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden bg-accent/10"
				>
					<div class="h-full w-1/3 animate-[shimmer_1s_ease-in-out_infinite] bg-accent/40 rounded-full"></div>
				</div>
			{/if}

			<table class="w-full text-sm {refreshing ? 'opacity-60' : 'opacity-100'} transition-opacity duration-200">
				<thead>
					<tr class="border-b border-border bg-surface-secondary text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
						<th class="w-8 px-3 py-2.5"></th>
						<th class="px-3 py-2.5">Type</th>
						<th class="px-3 py-2.5">Status</th>
						<th class="px-3 py-2.5">Progress</th>
						<th class="px-3 py-2.5">Created</th>
						<th class="px-3 py-2.5">Duration</th>
						<th class="px-3 py-2.5">Error</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each paginatedJobs as job (job.id)}
						{@const isExpanded = expandedJobId === job.id}
						<!-- Main row -->
						<tr
							class="cursor-pointer transition-colors hover:bg-surface-hover/50 {isExpanded ? 'bg-surface-secondary/50' : ''}"
							onclick={() => toggleJobExpand(job.id)}
						>
							<td class="px-3 py-2.5 text-text-secondary">
								{#if isExpanded}
									<ChevronDown size={14} />
								{:else}
									<ChevronRight size={14} />
								{/if}
							</td>
							<td class="px-3 py-2.5 font-medium text-text-primary">
								{formatJobType(job.job_type)}
							</td>
							<td class="px-3 py-2.5">
								<span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium {statusBadgeClass(job.status)}">
									{#if job.status === 'pending'}
										<Clock size={11} />
									{:else if job.status === 'running'}
										<Loader2 size={11} class="animate-spin" />
									{:else if job.status === 'completed'}
										<CheckCircle size={11} />
									{:else if job.status === 'failed'}
										<AlertCircle size={11} />
									{:else if job.status === 'cancelled'}
										<XCircle size={11} />
									{/if}
									{statusLabel(job.status)}
								</span>
							</td>
							<td class="px-3 py-2.5">
								{#if job.status === 'running'}
									<div class="flex items-center gap-2">
										<div class="h-1.5 w-24 overflow-hidden rounded-full bg-surface-secondary">
											<div
												class="h-full rounded-full bg-amber-500 transition-all duration-300"
												style="width: {job.progress_pct}%"
											></div>
										</div>
										<span class="text-xs text-text-secondary">{job.progress_pct}%</span>
									</div>
								{:else if job.status === 'completed'}
									<span class="text-xs text-text-secondary">100%</span>
								{:else}
									<span class="text-xs text-text-secondary">--</span>
								{/if}
							</td>
							<td class="px-3 py-2.5 text-text-secondary" title={formatFullTimestamp(job.created_at)}>
								{formatRelativeTime(job.created_at)}
							</td>
							<td class="px-3 py-2.5 text-text-secondary">
								{computeDuration(job)}
							</td>
							<td class="max-w-[200px] truncate px-3 py-2.5 text-text-secondary" title={job.error ?? ''}>
								{#if job.error}
									<span class="text-red-500">{job.error}</span>
								{:else}
									--
								{/if}
							</td>
						</tr>

						<!-- Expanded detail row -->
						{#if isExpanded}
							<tr>
								<td colspan="7" class="border-t border-border/50 bg-surface-secondary/30 p-0">
									<div transition:slide={{ duration: 150 }} class="px-6 py-4">
										{#if loadingDetail}
											<div class="flex items-center gap-2 py-4 text-text-secondary">
												<Loader2 size={14} class="animate-spin" />
												Loading details...
											</div>
										{:else if expandedJob}
											<div class="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
												<!-- Left column -->
												<div class="space-y-3">
													<div>
														<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Job ID</span>
														<p class="mt-0.5 font-mono text-xs text-text-primary">{expandedJob.id}</p>
													</div>
													<div>
														<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Type</span>
														<p class="mt-0.5 text-text-primary">{formatJobType(expandedJob.job_type)}</p>
													</div>
													<div>
														<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Progress Message</span>
														<p class="mt-0.5 text-text-primary">{expandedJob.progress_message || '--'}</p>
													</div>
													<div>
														<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Created</span>
														<p class="mt-0.5 text-text-primary">{formatFullTimestamp(expandedJob.created_at)}</p>
													</div>
													<div>
														<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Started</span>
														<p class="mt-0.5 text-text-primary">{formatFullTimestamp(expandedJob.started_at)}</p>
													</div>
													<div>
														<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Completed</span>
														<p class="mt-0.5 text-text-primary">{formatFullTimestamp(expandedJob.completed_at)}</p>
													</div>
												</div>

												<!-- Right column -->
												<div class="space-y-3">
													{#if expandedJob.result}
														<div>
															<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Result</span>
															<pre class="mt-1 max-h-48 overflow-auto rounded-md border border-border bg-surface p-3 font-mono text-xs text-text-primary">{JSON.stringify(expandedJob.result, null, 2)}</pre>
														</div>
													{/if}
													{#if expandedJob.error}
														<div>
															<span class="text-xs font-medium uppercase tracking-wider text-text-secondary">Error</span>
															<pre class="mt-1 max-h-48 overflow-auto rounded-md border border-red-500/30 bg-red-500/5 p-3 font-mono text-xs text-red-500">{expandedJob.error}</pre>
														</div>
													{/if}
													{#if !expandedJob.result && !expandedJob.error}
														<div class="flex items-center gap-2 py-4 text-text-secondary">
															<span class="text-xs">No result or error data available</span>
														</div>
													{/if}
												</div>
											</div>
										{/if}
									</div>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>

			<!-- Pagination footer -->
			{#if filteredJobs.length > pageSize}
				<div class="flex items-center justify-between border-t border-border px-4 py-2">
					<span class="text-xs text-text-secondary">
						{(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filteredJobs.length)} of {filteredJobs.length}
					</span>
					<div class="flex items-center gap-1">
						<button
							type="button"
							disabled={currentPage <= 1}
							onclick={() => currentPage--}
							class="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-40"
						>
							Previous
						</button>
						<span class="px-2 text-xs text-text-secondary">Page {currentPage} of {totalPages}</span>
						<button
							type="button"
							disabled={currentPage >= totalPages}
							onclick={() => currentPage++}
							class="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-40"
						>
							Next
						</button>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	@keyframes shimmer {
		0% { transform: translateX(-100%); }
		100% { transform: translateX(400%); }
	}
</style>
