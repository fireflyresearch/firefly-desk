<!--
  ProcessExplorer.svelte - Process discovery management and visualization.

  Split-layout admin view with a searchable/filterable process list sidebar on
  the left and a SvelteFlow canvas + detail panel on the right. Allows admins
  to browse discovered business processes, visualize step graphs, edit steps,
  verify processes, trigger re-discovery jobs, and toggle auto-analysis.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Loader2,
		X,
		Save,
		CheckCircle2,
		RefreshCw,
		GitBranch,
		Cog,
		Monitor,
		FileText,
		Tag,
		ChevronRight,
		AlertCircle,
		ToggleLeft,
		ToggleRight,
		Sparkles,
		Clock,
		ArrowRight,
		Filter,
		Brain,
		Database,
		Merge,
		CircleCheck,
		CircleX
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import RichEditor from '$lib/components/shared/RichEditor.svelte';
	import { parseSSEStream } from '$lib/services/sse.js';
	import FlowCanvas from '$lib/components/flow/FlowCanvas.svelte';
	import {
		toProcessFlowNodes,
		toProcessFlowEdges,
		layoutDagre
	} from '$lib/components/flow/flow-utils.js';
	import type {
		FlowNode as FlowNodeType,
		FlowEdge as FlowEdgeType,
		ProcessStep,
		ProcessDependency
	} from '$lib/components/flow/flow-types.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface BusinessProcess {
		id: string;
		name: string;
		description: string;
		category: string;
		steps: ProcessStep[];
		dependencies: ProcessDependency[];
		source: string;
		confidence: number;
		status: string;
		tags: string[];
		created_at: string;
		updated_at: string;
	}

	interface AnalysisSettings {
		auto_analyze: boolean;
	}

	interface DiscoverResponse {
		job_id: string;
		status: string;
		progress_pct: number;
	}

	type ProcessStatus = 'discovered' | 'verified' | 'modified' | 'archived';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let processes = $state<BusinessProcess[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Sidebar filters
	let searchQuery = $state('');
	let statusFilter = $state<ProcessStatus | 'all'>('all');

	// Selected process
	let selectedProcess = $state<BusinessProcess | null>(null);
	let loadingDetail = $state(false);

	// Flow graph
	let flowNodes = $state<FlowNodeType[]>([]);
	let flowEdges = $state<FlowEdgeType[]>([]);

	// Step edit panel
	let editingStep = $state<ProcessStep | null>(null);
	let stepForm = $state({
		name: '',
		description: '',
		system_id: '',
		inputs: '',
		outputs: ''
	});
	let savingStep = $state(false);

	// Verify / re-discover
	let verifying = $state(false);

	// Discovery job
	let discoveryJobId = $state<string | null>(null);
	let discoveryJobStatus = $state<string | null>(null);
	let discoveryJobProgress = $state(0);
	let discoveryProgressMessage = $state('');

	// Discovery conversation log
	interface DiscoveryLogEntry {
		message: string;
		pct: number;
		timestamp: Date;
		type: 'scan' | 'context' | 'llm' | 'result' | 'merge' | 'done' | 'error' | 'info';
	}
	let discoveryLog = $state<DiscoveryLogEntry[]>([]);
	let discoveryLogEl: HTMLDivElement | null = $state(null);

	// Auto-analyze toggle
	let autoAnalyze = $state(false);
	let loadingAutoAnalyze = $state(true);
	let togglingAutoAnalyze = $state(false);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let filteredProcesses = $derived.by(() => {
		let result = processes;

		if (statusFilter !== 'all') {
			result = result.filter((p) => p.status === statusFilter);
		}

		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(
				(p) =>
					p.name.toLowerCase().includes(q) ||
					p.description.toLowerCase().includes(q) ||
					p.category.toLowerCase().includes(q) ||
					p.tags.some((t) => t.toLowerCase().includes(q))
			);
		}

		return result;
	});

	let isDiscovering = $derived(
		discoveryJobStatus === 'pending' || discoveryJobStatus === 'running'
	);

	let editingStepIcon = $derived(editingStep ? stepTypeIcon(editingStep.step_type) : Cog);

	// -----------------------------------------------------------------------
	// Build flow graph when selected process changes
	// -----------------------------------------------------------------------

	$effect(() => {
		if (!selectedProcess || selectedProcess.steps.length === 0) {
			flowNodes = [];
			flowEdges = [];
			return;
		}

		const rawNodes = toProcessFlowNodes(selectedProcess.steps);
		const rawEdges = toProcessFlowEdges(selectedProcess.dependencies);

		flowNodes = layoutDagre(rawNodes, rawEdges, {
			nodeWidth: 200,
			nodeHeight: 60,
			horizontalGap: 60,
			verticalGap: 80,
			direction: 'TB'
		});

		flowEdges = rawEdges.map((edge) => ({
			...edge,
			markerEnd: 'arrowclosed'
		}));
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadProcesses() {
		loading = true;
		error = '';
		try {
			processes = await apiJson<BusinessProcess[]>('/processes');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load processes';
		} finally {
			loading = false;
		}
	}

	async function loadProcessDetail(id: string) {
		loadingDetail = true;
		error = '';
		editingStep = null;
		try {
			selectedProcess = await apiJson<BusinessProcess>(`/processes/${id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load process detail';
		} finally {
			loadingDetail = false;
		}
	}

	async function loadAnalysisSettings() {
		loadingAutoAnalyze = true;
		try {
			const settings = await apiJson<AnalysisSettings>('/settings/analysis');
			autoAnalyze = settings.auto_analyze;
		} catch {
			// Non-critical -- toggle simply remains off
		} finally {
			loadingAutoAnalyze = false;
		}
	}

	$effect(() => {
		loadProcesses();
		loadAnalysisSettings();
	});

	// -----------------------------------------------------------------------
	// Process selection
	// -----------------------------------------------------------------------

	function selectProcess(process: BusinessProcess) {
		if (selectedProcess?.id === process.id) return;
		loadProcessDetail(process.id);
	}

	function clearSelection() {
		selectedProcess = null;
		editingStep = null;
		flowNodes = [];
		flowEdges = [];
	}

	// -----------------------------------------------------------------------
	// Node click -> step edit
	// -----------------------------------------------------------------------

	function handleNodeClick(node: FlowNodeType) {
		if (!selectedProcess) return;
		const step = selectedProcess.steps.find((s) => s.id === node.id);
		if (step) {
			openStepEditor(step);
		}
	}

	function handlePaneClick() {
		editingStep = null;
	}

	function openStepEditor(step: ProcessStep) {
		editingStep = step;
		stepForm = {
			name: step.name,
			description: step.description ?? '',
			system_id: step.system_id ?? '',
			inputs: (step.inputs ?? []).join(', '),
			outputs: (step.outputs ?? []).join(', ')
		};
	}

	function closeStepEditor() {
		editingStep = null;
	}

	async function saveStep() {
		if (!selectedProcess || !editingStep) return;
		if (!stepForm.name.trim()) {
			error = 'Step name is required.';
			return;
		}
		savingStep = true;
		error = '';
		try {
			const payload = {
				name: stepForm.name,
				description: stepForm.description || null,
				system_id: stepForm.system_id || null,
				inputs: stepForm.inputs
					.split(',')
					.map((s) => s.trim())
					.filter(Boolean),
				outputs: stepForm.outputs
					.split(',')
					.map((s) => s.trim())
					.filter(Boolean)
			};
			await apiJson(`/processes/${selectedProcess.id}/steps/${editingStep.id}`, {
				method: 'PUT',
				body: JSON.stringify(payload)
			});
			editingStep = null;
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save step';
		} finally {
			savingStep = false;
		}
	}

	// -----------------------------------------------------------------------
	// Verify process
	// -----------------------------------------------------------------------

	async function verifyProcess() {
		if (!selectedProcess) return;
		verifying = true;
		error = '';
		try {
			await apiFetch(`/processes/${selectedProcess.id}/verify`, { method: 'POST' });
			await loadProcessDetail(selectedProcess.id);
			await loadProcesses();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to verify process';
		} finally {
			verifying = false;
		}
	}

	// -----------------------------------------------------------------------
	// Re-discover
	// -----------------------------------------------------------------------

	function classifyLogEntry(message: string): DiscoveryLogEntry['type'] {
		const lower = message.toLowerCase();
		if (lower.includes('scanning') || lower.includes('gathering')) return 'scan';
		if (lower.includes('context gathered')) return 'context';
		if (lower.includes('sending') && lower.includes('llm')) return 'llm';
		if (lower.includes('calling llm') || lower.includes('analysis')) return 'llm';
		if (lower.includes('identified')) return 'result';
		if (lower.includes('merging') || lower.includes('merge complete')) return 'merge';
		if (lower.includes('complete') || lower.includes('discovery complete')) return 'done';
		if (lower.includes('failed') || lower.includes('error')) return 'error';
		if (lower.includes('skipped') || lower.includes('no llm')) return 'error';
		return 'info';
	}

	async function triggerRediscover() {
		error = '';
		discoveryProgressMessage = '';
		discoveryLog = [];
		try {
			const resp = await apiJson<DiscoverResponse>('/processes/discover', { method: 'POST' });
			discoveryJobId = resp.job_id;
			discoveryJobStatus = resp.status;
			discoveryJobProgress = resp.progress_pct ?? 0;

			const response = await apiFetch(`/jobs/${resp.job_id}/stream`);
			await parseSSEStream(
				response,
				(msg) => {
					if (msg.event === 'job_progress') {
						discoveryJobStatus = (msg.data.status as string) ?? discoveryJobStatus;
						discoveryJobProgress = (msg.data.progress_pct as number) ?? discoveryJobProgress;
						if (msg.data.progress_message) {
							const message = msg.data.progress_message as string;
							discoveryProgressMessage = message;
							// Accumulate into conversation log (skip duplicates)
							if (!discoveryLog.some((e) => e.message === message)) {
								discoveryLog = [
									...discoveryLog,
									{
										message,
										pct: msg.data.progress_pct as number,
										timestamp: new Date(),
										type: classifyLogEntry(message)
									}
								];
								// Auto-scroll to bottom
								requestAnimationFrame(() => {
									discoveryLogEl?.scrollTo({
										top: discoveryLogEl.scrollHeight,
										behavior: 'smooth'
									});
								});
							}
						}
					} else if (msg.event === 'done') {
						discoveryJobStatus = msg.data.status as string;
						if (msg.data.error) {
							const errMsg = `Discovery failed: ${msg.data.error as string}`;
							error = errMsg;
							discoveryLog = [
								...discoveryLog,
								{
									message: errMsg,
									pct: 100,
									timestamp: new Date(),
									type: 'error'
								}
							];
						}
					}
				},
				(err) => {
					error = `Stream error: ${err.message}`;
				},
				async () => {
					// Stream ended -- update final state
					if (discoveryJobStatus !== 'failed' && discoveryJobStatus !== 'cancelled') {
						discoveryJobStatus = 'completed';
					}
					discoveryProgressMessage = '';
					await loadProcesses();
					if (selectedProcess) {
						await loadProcessDetail(selectedProcess.id);
					}
				}
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to start discovery';
		}
	}

	// -----------------------------------------------------------------------
	// Auto-analyze toggle
	// -----------------------------------------------------------------------

	async function toggleAutoAnalyze() {
		togglingAutoAnalyze = true;
		const next = !autoAnalyze;
		try {
			await apiJson('/settings/analysis', {
				method: 'PUT',
				body: JSON.stringify({ auto_analyze: next })
			});
			autoAnalyze = next;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update setting';
		} finally {
			togglingAutoAnalyze = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function confidenceColor(confidence: number): string {
		if (confidence >= 0.8) return 'bg-success/10 text-success';
		if (confidence >= 0.5) return 'bg-warning/10 text-warning';
		return 'bg-danger/10 text-danger';
	}

	function statusBadge(status: string): string {
		switch (status) {
			case 'verified':
				return 'bg-success/10 text-success';
			case 'discovered':
				return 'bg-accent/10 text-accent';
			case 'modified':
				return 'bg-warning/10 text-warning';
			case 'archived':
				return 'bg-text-secondary/10 text-text-secondary';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
		}
	}

	function sourceLabel(source: string): string {
		switch (source) {
			case 'auto_discovered':
				return 'Auto-discovered';
			case 'manual':
				return 'Manual';
			case 'imported':
				return 'Imported';
			default:
				return source;
		}
	}

	function formatDate(dateStr: string): string {
		if (!dateStr) return '--';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	const statusOptions: { value: ProcessStatus | 'all'; label: string }[] = [
		{ value: 'all', label: 'All' },
		{ value: 'discovered', label: 'Discovered' },
		{ value: 'verified', label: 'Verified' },
		{ value: 'modified', label: 'Modified' },
		{ value: 'archived', label: 'Archived' }
	];

	function stepTypeIcon(stepType?: string): typeof Cog {
		if (!stepType) return Cog;
		const lower = stepType.toLowerCase();
		if (lower === 'system' || lower === 'integration') return Monitor;
		if (lower === 'document' || lower === 'form') return FileText;
		return Cog;
	}

	function logEntryIcon(type: DiscoveryLogEntry['type']): typeof Cog {
		switch (type) {
			case 'scan':
				return Search;
			case 'context':
				return Database;
			case 'llm':
				return Brain;
			case 'result':
				return Sparkles;
			case 'merge':
				return Merge;
			case 'done':
				return CircleCheck;
			case 'error':
				return CircleX;
			default:
				return Cog;
		}
	}

	function logEntryColor(type: DiscoveryLogEntry['type']): string {
		switch (type) {
			case 'scan':
				return 'text-accent';
			case 'context':
				return 'text-accent';
			case 'llm':
				return 'text-warning';
			case 'result':
				return 'text-success';
			case 'merge':
				return 'text-accent';
			case 'done':
				return 'text-success';
			case 'error':
				return 'text-danger';
			default:
				return 'text-text-secondary';
		}
	}

	function formatTime(date: Date): string {
		return date.toLocaleTimeString('en-US', {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: false
		});
	}
</script>

<div class="flex h-full">
	<!-- ================================================================= -->
	<!-- Left sidebar: process list                                         -->
	<!-- ================================================================= -->
	<div class="flex w-72 shrink-0 flex-col border-r border-border bg-surface-secondary">
		<!-- Header -->
		<div class="border-b border-border/50 px-4 py-3">
			<h1 class="text-sm font-semibold text-text-primary">Processes</h1>
			<p class="text-xs text-text-secondary">Discovered business processes</p>
		</div>

		<!-- Search -->
		<div class="border-b border-border/50 px-3 py-2">
			<div class="relative">
				<Search
					size={14}
					class="absolute top-1/2 left-2.5 -translate-y-1/2 text-text-secondary"
				/>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search processes..."
					class="w-full rounded-md border border-border bg-surface py-1.5 pr-3 pl-8 text-xs text-text-primary outline-none focus:border-accent"
				/>
			</div>
		</div>

		<!-- Status filter -->
		<div class="flex items-center gap-1 overflow-x-auto border-b border-border/50 px-3 py-2">
			<Filter size={12} class="flex-shrink-0 text-text-secondary" />
			{#each statusOptions as option}
				<button
					type="button"
					onclick={() => (statusFilter = option.value)}
					class="flex-shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors
						{statusFilter === option.value
						? 'border-accent/30 bg-accent/10 text-accent'
						: 'border-border text-text-secondary hover:bg-surface-hover'}"
				>
					{option.label}
				</button>
			{/each}
		</div>

		<!-- Process list -->
		<div class="flex-1 overflow-y-auto">
			{#if loading}
				<div class="flex items-center justify-center py-12">
					<Loader2 size={20} class="animate-spin text-text-secondary" />
				</div>
			{:else if filteredProcesses.length === 0}
				<div class="px-4 py-8 text-center text-xs text-text-secondary">
					{searchQuery || statusFilter !== 'all'
						? 'No processes match your filters.'
						: 'No processes discovered yet.'}
				</div>
			{:else}
				<ul class="flex flex-col gap-0.5 p-2">
					{#each filteredProcesses as process}
						{@const isSelected = selectedProcess?.id === process.id}
						<li>
							<button
								type="button"
								onclick={() => selectProcess(process)}
								class="flex w-full flex-col gap-1 rounded-md px-3 py-2.5 text-left transition-colors
									{isSelected
									? 'bg-accent/10 ring-1 ring-accent/30'
									: 'hover:bg-surface-hover'}"
							>
								<div class="flex items-center gap-2">
									<GitBranch
										size={14}
										class={isSelected ? 'text-accent' : 'text-text-secondary'}
									/>
									<span
										class="flex-1 truncate text-xs font-medium {isSelected
											? 'text-accent'
											: 'text-text-primary'}"
									>
										{process.name}
									</span>
								</div>
								<div class="flex items-center gap-1.5 pl-5">
									<span
										class="rounded-full px-1.5 py-0.5 text-[10px] font-medium {statusBadge(
											process.status
										)}"
									>
										{process.status}
									</span>
									<span
										class="rounded-full px-1.5 py-0.5 text-[10px] font-medium {confidenceColor(
											process.confidence
										)}"
									>
										{Math.round(process.confidence * 100)}%
									</span>
									{#if process.category}
										<span class="truncate text-[10px] text-text-secondary">
											{process.category}
										</span>
									{/if}
								</div>
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Auto-analyze toggle and re-discover at bottom -->
		<div class="border-t border-border/50 px-3 py-3">
			<!-- Auto-analyze -->
			<div class="mb-2 flex items-center justify-between">
				<span class="text-xs text-text-secondary">Auto-analyze</span>
				<button
					type="button"
					onclick={toggleAutoAnalyze}
					disabled={loadingAutoAnalyze || togglingAutoAnalyze}
					class="text-text-secondary transition-colors hover:text-text-primary disabled:opacity-50"
					title={autoAnalyze ? 'Auto-analyze is on' : 'Auto-analyze is off'}
				>
					{#if loadingAutoAnalyze || togglingAutoAnalyze}
						<Loader2 size={18} class="animate-spin" />
					{:else if autoAnalyze}
						<ToggleRight size={22} class="text-accent" />
					{:else}
						<ToggleLeft size={22} />
					{/if}
				</button>
			</div>

			<!-- Re-discover button -->
			<button
				type="button"
				onclick={triggerRediscover}
				disabled={isDiscovering}
				class="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
			>
				{#if isDiscovering}
					<Loader2 size={14} class="animate-spin" />
					Discovering...
				{:else}
					<RefreshCw size={14} />
					Re-discover Processes
				{/if}
			</button>

			<!-- Job progress indicator -->
			{#if isDiscovering}
				<div class="mt-2">
					{#if discoveryProgressMessage}
						<p class="mb-1 truncate text-[10px] text-text-secondary">{discoveryProgressMessage}</p>
					{/if}
					<div class="h-1.5 w-full overflow-hidden rounded-full bg-surface">
						<div
							class="h-full rounded-full bg-accent transition-all duration-500"
							style="width: {discoveryJobProgress}%"
						></div>
					</div>
				</div>
			{/if}
		</div>
	</div>

	<!-- ================================================================= -->
	<!-- Right main area                                                    -->
	<!-- ================================================================= -->
	<div class="flex flex-1 flex-col overflow-hidden">
		<!-- Error banner -->
		{#if error}
			<div
				class="mx-4 mt-3 flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger"
			>
				<AlertCircle size={16} />
				<span class="flex-1">{error}</span>
				<button
					type="button"
					onclick={() => (error = '')}
					class="text-danger/60 hover:text-danger"
				>
					<X size={14} />
				</button>
			</div>
		{/if}

		{#if !selectedProcess && discoveryLog.length > 0}
			<!-- Discovery conversation timeline -->
			<div class="flex flex-1 flex-col overflow-hidden">
				<div class="border-b border-border px-5 py-3">
					<div class="flex items-center gap-2">
						<Brain size={18} class="text-accent" />
						<h2 class="text-base font-semibold text-text-primary">Process Discovery</h2>
						{#if isDiscovering}
							<span
								class="ml-2 inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
							>
								<Loader2 size={12} class="animate-spin" />
								Running
							</span>
						{:else if discoveryJobStatus === 'completed'}
							<span
								class="ml-2 inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
							>
								<CircleCheck size={12} />
								Complete
							</span>
						{:else if discoveryJobStatus === 'failed'}
							<span
								class="ml-2 inline-flex items-center gap-1 rounded-full bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger"
							>
								<CircleX size={12} />
								Failed
							</span>
						{/if}
					</div>
				</div>

				<!-- Scrollable log -->
				<div
					bind:this={discoveryLogEl}
					class="flex-1 overflow-y-auto px-5 py-4"
				>
					<div class="mx-auto max-w-2xl space-y-1">
						{#each discoveryLog as entry, i}
							{@const Icon = logEntryIcon(entry.type)}
							{@const color = logEntryColor(entry.type)}
							<div
								class="group flex gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-hover/50"
							>
								<!-- Icon column -->
								<div class="flex flex-col items-center pt-0.5">
									<div
										class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-secondary {color}"
									>
										<Icon size={14} />
									</div>
									{#if i < discoveryLog.length - 1}
										<div class="mt-1 w-px flex-1 bg-border/50"></div>
									{/if}
								</div>

								<!-- Content -->
								<div class="min-w-0 flex-1 pb-2">
									<p class="text-sm leading-relaxed text-text-primary">
										{entry.message}
									</p>
									<p class="mt-0.5 text-[10px] text-text-secondary/60">
										{formatTime(entry.timestamp)} · {entry.pct}%
									</p>
								</div>
							</div>
						{/each}

						{#if isDiscovering}
							<!-- Typing indicator -->
							<div class="flex gap-3 px-3 py-2.5">
								<div
									class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-secondary text-accent"
								>
									<Loader2 size={14} class="animate-spin" />
								</div>
								<div class="flex items-center pt-1">
									<span class="text-xs text-text-secondary/60">Processing...</span>
								</div>
							</div>
						{/if}
					</div>
				</div>

				<!-- Progress bar at bottom -->
				{#if isDiscovering || discoveryJobStatus === 'completed'}
					<div class="border-t border-border px-5 py-3">
						<div class="h-1.5 w-full overflow-hidden rounded-full bg-surface-secondary">
							<div
								class="h-full rounded-full transition-all duration-500 {discoveryJobStatus === 'completed'
									? 'bg-success'
									: discoveryJobStatus === 'failed'
										? 'bg-danger'
										: 'bg-accent'}"
								style="width: {discoveryJobProgress}%"
							></div>
						</div>
						<div class="mt-1 flex items-center justify-between text-[10px] text-text-secondary/60">
							<span>{discoveryProgressMessage || (discoveryJobStatus === 'completed' ? 'Discovery complete' : '')}</span>
							<span>{discoveryJobProgress}%</span>
						</div>
					</div>
				{/if}
			</div>
		{:else if !selectedProcess}
			<!-- Empty state -->
			<div class="flex flex-1 flex-col items-center justify-center gap-3 text-text-secondary">
				<GitBranch size={48} strokeWidth={1} class="opacity-30" />
				<p class="text-sm">Select a process to view its steps and dependencies</p>
				<p class="text-xs">Or trigger a new discovery job from the sidebar</p>
			</div>
		{:else if loadingDetail}
			<div class="flex flex-1 items-center justify-center">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else}
			<!-- Process detail header -->
			<div class="border-b border-border px-5 py-3">
				<div class="flex items-start justify-between gap-4">
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-2">
							<h2 class="truncate text-base font-semibold text-text-primary">
								{selectedProcess.name}
							</h2>
							<span
								class="flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {statusBadge(
									selectedProcess.status
								)}"
							>
								{selectedProcess.status}
							</span>
							<span
								class="flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {confidenceColor(
									selectedProcess.confidence
								)}"
							>
								{Math.round(selectedProcess.confidence * 100)}% confidence
							</span>
						</div>
						{#if selectedProcess.description}
							<p class="mt-1 text-xs leading-relaxed text-text-secondary">
								{selectedProcess.description}
							</p>
						{/if}
						<div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
							{#if selectedProcess.category}
								<span class="flex items-center gap-1">
									<Cog size={12} />
									{selectedProcess.category}
								</span>
							{/if}
							<span class="flex items-center gap-1">
								<Sparkles size={12} />
								{sourceLabel(selectedProcess.source)}
							</span>
							<span class="flex items-center gap-1">
								<Clock size={12} />
								{formatDate(selectedProcess.updated_at)}
							</span>
							{#if selectedProcess.steps.length > 0}
								<span>{selectedProcess.steps.length} steps</span>
							{/if}
							{#if selectedProcess.tags.length > 0}
								<span class="flex items-center gap-1">
									<Tag size={12} />
									{#each selectedProcess.tags as tag}
										<span
											class="rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary"
										>
											{tag}
										</span>
									{/each}
								</span>
							{/if}
						</div>
					</div>

					<!-- Actions -->
					<div class="flex items-center gap-2">
						{#if selectedProcess.status !== 'verified'}
							<button
								type="button"
								onclick={verifyProcess}
								disabled={verifying}
								class="inline-flex items-center gap-1.5 rounded-md border border-success/40 bg-success/5 px-3 py-1.5 text-xs font-medium text-success transition-colors hover:bg-success/10 disabled:opacity-50"
							>
								{#if verifying}
									<Loader2 size={14} class="animate-spin" />
								{:else}
									<CheckCircle2 size={14} />
								{/if}
								Verify
							</button>
						{:else}
							<span class="inline-flex items-center gap-1 text-xs font-medium text-success">
								<CheckCircle2 size={14} />
								Verified
							</span>
						{/if}
						<button
							type="button"
							onclick={() => clearSelection()}
							class="rounded p-1.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
							title="Close"
						>
							<X size={16} />
						</button>
					</div>
				</div>
			</div>

			<!-- Canvas and step editor area -->
			<div class="flex flex-1 overflow-hidden">
				<!-- SvelteFlow canvas -->
				<div class="relative flex-1 overflow-hidden">
					{#if selectedProcess.steps.length === 0}
						<div
							class="flex h-full flex-col items-center justify-center gap-2 text-text-secondary"
						>
							<GitBranch size={36} strokeWidth={1} class="opacity-30" />
							<p class="text-sm">No steps in this process</p>
						</div>
					{:else}
						<FlowCanvas
							nodes={flowNodes}
							edges={flowEdges}
							fitView={true}
							interactive={true}
							options={{
								minimap: true,
								controls: true,
								background: 'dots',
								minZoom: 0.1,
								maxZoom: 5
							}}
							onNodeClick={handleNodeClick}
							onPaneClick={handlePaneClick}
						/>

						<!-- Step count overlay -->
						<div
							class="pointer-events-none absolute top-3 right-3 flex gap-2"
						>
							<div
								class="pointer-events-auto rounded-md border border-border bg-surface/90 px-3 py-2 text-xs shadow-sm backdrop-blur-sm"
							>
								<div class="font-medium text-text-secondary">Steps</div>
								<div class="text-lg font-semibold text-text-primary">
									{selectedProcess.steps.length}
								</div>
							</div>
							<div
								class="pointer-events-auto rounded-md border border-border bg-surface/90 px-3 py-2 text-xs shadow-sm backdrop-blur-sm"
							>
								<div class="font-medium text-text-secondary">Dependencies</div>
								<div class="text-lg font-semibold text-text-primary">
									{selectedProcess.dependencies.length}
								</div>
							</div>
						</div>

						<!-- Click hint -->
						{#if !editingStep}
							<div
								class="pointer-events-none absolute bottom-3 left-3 rounded-md border border-border bg-surface/90 px-3 py-1.5 text-xs text-text-secondary backdrop-blur-sm"
							>
								Click a step node to edit
							</div>
						{/if}
					{/if}
				</div>

				<!-- Step edit panel (slide-out) -->
				{#if editingStep}
					<div
						class="flex w-80 shrink-0 flex-col border-l border-border bg-surface"
					>
						<!-- Panel header -->
						<div
							class="flex items-center justify-between border-b border-border px-4 py-2.5"
						>
							<h4 class="text-sm font-semibold text-text-primary">Edit Step</h4>
							<button
								type="button"
								onclick={closeStepEditor}
								class="rounded p-1 text-text-secondary hover:text-text-primary"
								title="Close"
							>
								<X size={14} />
							</button>
						</div>

						<!-- Panel body -->
						<div class="flex-1 overflow-y-auto p-4">
							<form
								onsubmit={(e) => {
									e.preventDefault();
									saveStep();
								}}
								class="flex flex-col gap-3"
							>
								<!-- Step name -->
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Name</span>
									<input
										type="text"
										bind:value={stepForm.name}
										required
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<!-- Description -->
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Description</span>
									<RichEditor
										value={stepForm.description}
										placeholder="Step description..."
										mode="compact"
										minHeight="80px"
										onchange={(md) => (stepForm.description = md)}
									/>
								</label>

								<!-- System ID -->
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">System ID</span>
									<input
										type="text"
										bind:value={stepForm.system_id}
										placeholder="e.g. crm-system"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<!-- Step type + order (read-only info) -->
								<div class="rounded-md border border-border bg-surface-secondary p-3">
									<div class="flex flex-col gap-1.5 text-xs">
										<div class="flex items-center gap-2">
											<span class="font-medium text-text-secondary">Type:</span>
											<span class="flex items-center gap-1 text-text-primary">
												{#if editingStepIcon}
													{@const StepIcon = editingStepIcon}
													<StepIcon size={12} />
												{/if}
												{editingStep.step_type ?? 'general'}
											</span>
										</div>
										<div class="flex items-center gap-2">
											<span class="font-medium text-text-secondary">Order:</span>
											<span class="text-text-primary">{editingStep.order}</span>
										</div>
										{#if editingStep.endpoint_id}
											<div class="flex items-center gap-2">
												<span class="font-medium text-text-secondary">Endpoint:</span>
												<span class="font-mono text-text-primary">
													{editingStep.endpoint_id}
												</span>
											</div>
										{/if}
									</div>
								</div>

								<!-- Inputs -->
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">
										Inputs (comma-separated)
									</span>
									<input
										type="text"
										bind:value={stepForm.inputs}
										placeholder="e.g. customer_id, order_data"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<!-- Outputs -->
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">
										Outputs (comma-separated)
									</span>
									<input
										type="text"
										bind:value={stepForm.outputs}
										placeholder="e.g. confirmation, receipt"
										class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<!-- Save / Cancel -->
								<div class="flex justify-end gap-2 pt-1">
									<button
										type="button"
										onclick={closeStepEditor}
										class="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
									>
										Cancel
									</button>
									<button
										type="submit"
										disabled={savingStep}
										class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
									>
										{#if savingStep}
											<Loader2 size={12} class="animate-spin" />
										{:else}
											<Save size={12} />
										{/if}
										Save Step
									</button>
								</div>
							</form>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
