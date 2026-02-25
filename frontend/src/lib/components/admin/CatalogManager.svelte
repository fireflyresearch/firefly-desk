<!--
  CatalogManager.svelte - CRUD interface for external system catalog.

  Lists systems in a table with expandable endpoint rows. Uses the
  SystemWizard modal for creating and editing systems.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Pencil,
		Trash2,
		ChevronDown,
		ChevronRight,
		Loader2,
		FileUp,
		Sparkles,
		X,
		CheckCircle2,
		AlertCircle
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import { parseSSEStream } from '$lib/services/sse.js';
	import SystemWizard from './SystemWizard.svelte';
	import EndpointWizard from './EndpointWizard.svelte';
	import OpenAPIImportWizard from './OpenAPIImportWizard.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Endpoint {
		id: string;
		system_id: string;
		name: string;
		method: string;
		path: string;
		description: string;
		risk_level?: string;
		protocol_type?: string;
	}

	interface System {
		id: string;
		name: string;
		base_url: string;
		status: string;
		tags: string[];
	}

	interface SystemFull {
		id: string;
		name: string;
		description: string;
		base_url: string;
		auth_config: {
			auth_type: string;
			credential_id: string;
			token_url?: string | null;
			scopes?: string[] | null;
			auth_headers?: Record<string, string> | null;
			auth_params?: Record<string, string> | null;
		};
		health_check_path: string | null;
		tags: string[];
		status: string;
		agent_enabled: boolean;
		metadata: Record<string, unknown>;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let systems = $state<System[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Expanded rows (system IDs whose endpoints are visible)
	let expandedIds = $state<Set<string>>(new Set());
	let endpointCache = $state<Record<string, Endpoint[]>>({});

	// System Wizard state
	let showForm = $state(false);
	let saving = $state(false);
	let editingSystemFull = $state<SystemFull | null>(null);

	// OpenAPI Import Wizard state
	let showImportWizard = $state(false);

	// Endpoint Wizard state
	let showEndpointWizard = $state(false);
	let endpointWizardSystemId = $state('');
	let editingEndpoint = $state<any | null>(null);

	// Detection state
	let detectJobId = $state<string | null>(null);
	let detectJobStatus = $state<string | null>(null);
	let detectProgress = $state(0);
	let detectionLog = $state<DetectionLogEntry[]>([]);
	let showDetectionLog = $state(false);
	let detectionLogEl: HTMLDivElement | null = $state(null);

	interface DetectionLogEntry {
		message: string;
		pct: number;
		timestamp: Date;
		type: 'scan' | 'context' | 'llm' | 'result' | 'merge' | 'done' | 'error' | 'info';
	}

	let isDetecting = $derived(
		detectJobStatus === 'pending' || detectJobStatus === 'running'
	);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadSystems() {
		loading = true;
		error = '';
		try {
			systems = await apiJson<System[]>('/catalog/systems');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load systems';
		} finally {
			loading = false;
		}
	}

	async function loadEndpoints(systemId: string) {
		if (endpointCache[systemId]) return;
		try {
			const eps = await apiJson<Endpoint[]>(`/catalog/systems/${systemId}/endpoints`);
			endpointCache[systemId] = eps;
		} catch {
			endpointCache[systemId] = [];
		}
	}

	// Initial load
	$effect(() => {
		loadSystems();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function toggleExpand(systemId: string) {
		const next = new Set(expandedIds);
		if (next.has(systemId)) {
			next.delete(systemId);
		} else {
			next.add(systemId);
			loadEndpoints(systemId);
		}
		expandedIds = next;
	}

	function openAddForm() {
		editingSystemFull = null;
		showForm = true;
	}

	async function openEditForm(system: System) {
		error = '';
		try {
			editingSystemFull = await apiJson<SystemFull>(`/catalog/systems/${system.id}`);
			showForm = true;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load system details';
		}
	}

	function closeWizard() {
		showForm = false;
		editingSystemFull = null;
	}

	async function onWizardSaved() {
		showForm = false;
		editingSystemFull = null;
		await loadSystems();
	}

	async function deleteSystem(id: string) {
		error = '';
		try {
			await apiJson(`/catalog/systems/${id}`, { method: 'DELETE' });
			await loadSystems();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete system';
		}
	}

	// -----------------------------------------------------------------------
	// Endpoint actions
	// -----------------------------------------------------------------------

	function openAddEndpoint(systemId: string) {
		endpointWizardSystemId = systemId;
		editingEndpoint = null;
		showEndpointWizard = true;
	}

	async function openEditEndpoint(endpoint: Endpoint) {
		endpointWizardSystemId = endpoint.system_id;
		editingEndpoint = endpoint;
		showEndpointWizard = true;
	}

	function closeEndpointWizard() {
		showEndpointWizard = false;
		editingEndpoint = null;
	}

	async function onEndpointSaved() {
		showEndpointWizard = false;
		editingEndpoint = null;
		// Clear endpoint cache to force reload
		endpointCache = {};
		await loadSystems();
	}

	async function deleteEndpoint(endpointId: string, systemId: string) {
		error = '';
		try {
			await apiJson(`/catalog/endpoints/${endpointId}`, { method: 'DELETE' });
			// Invalidate cache for this system
			delete endpointCache[systemId];
			endpointCache = { ...endpointCache };
			await loadEndpoints(systemId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete endpoint';
		}
	}

	// -----------------------------------------------------------------------
	// System Detection
	// -----------------------------------------------------------------------

	function classifyLogEntry(message: string): DetectionLogEntry['type'] {
		const lower = message.toLowerCase();
		if (lower.includes('scanning') || lower.includes('scan')) return 'scan';
		if (lower.includes('context gathered') || lower.includes('context')) return 'context';
		if (lower.includes('sending') || lower.includes('llm') || lower.includes('analysis')) return 'llm';
		if (lower.includes('identified') || lower.includes('discovered')) return 'result';
		if (lower.includes('merging') || lower.includes('merge') || lower.includes('creating')) return 'merge';
		if (lower.includes('complete') || lower.includes('discovery complete')) return 'done';
		if (lower.includes('failed') || lower.includes('error') || lower.includes('skipped')) return 'error';
		return 'info';
	}

	async function triggerDetectSystems() {
		error = '';
		detectionLog = [];
		showDetectionLog = true;
		try {
			const resp = await apiJson<{ job_id: string; status: string; progress_pct: number }>('/catalog/detect', { method: 'POST' });
			detectJobId = resp.job_id;
			detectJobStatus = resp.status;
			detectProgress = resp.progress_pct ?? 0;

			const response = await apiFetch(`/jobs/${resp.job_id}/stream`);
			await parseSSEStream(
				response,
				(msg) => {
					if (msg.event === 'job_progress') {
						detectJobStatus = (msg.data.status as string) ?? detectJobStatus;
						detectProgress = (msg.data.progress_pct as number) ?? detectProgress;
						if (msg.data.progress_message) {
							const message = msg.data.progress_message as string;
							if (!detectionLog.some((e) => e.message === message)) {
								detectionLog = [
									...detectionLog,
									{
										message,
										pct: msg.data.progress_pct as number,
										timestamp: new Date(),
										type: classifyLogEntry(message)
									}
								];
								requestAnimationFrame(() => {
									detectionLogEl?.scrollTo({
										top: detectionLogEl.scrollHeight,
										behavior: 'smooth'
									});
								});
							}
						}
					} else if (msg.event === 'done') {
						detectJobStatus = msg.data.status as string;
						if (msg.data.error) {
							error = `Detection failed: ${msg.data.error as string}`;
							detectionLog = [
								...detectionLog,
								{ message: `Detection failed: ${msg.data.error}`, pct: 100, timestamp: new Date(), type: 'error' }
							];
						}
					}
				},
				(err) => { error = `Stream error: ${err.message}`; },
				async () => {
					if (detectJobStatus !== 'failed' && detectJobStatus !== 'cancelled') {
						detectJobStatus = 'completed';
					}
					await loadSystems();
				}
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Detection failed';
			detectJobStatus = 'failed';
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	let confirmingDeleteId = $state<string | null>(null);
	let confirmingDeprecateId = $state<string | null>(null);
	let transitioning = $state(false);

	function startDelete(id: string) {
		confirmingDeleteId = id;
	}

	function cancelDeleteConfirm() {
		confirmingDeleteId = null;
	}

	async function confirmAndDelete(id: string) {
		confirmingDeleteId = null;
		await deleteSystem(id);
	}

	function statusVariant(status: string): string {
		switch (status) {
			case 'active':
				return 'bg-success/10 text-success';
			case 'draft':
				return 'bg-warning/10 text-warning';
			case 'disabled':
				return 'bg-text-secondary/10 text-text-secondary';
			case 'deprecated':
				return 'bg-danger/10 text-danger';
			case 'degraded':
				return 'bg-orange-400/10 text-orange-400';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
		}
	}

	// Note: 'active -> degraded' is omitted intentionally. The 'degraded'
	// status is set automatically by health-check monitoring, not by manual
	// user action. Only recovery transitions (degraded -> active/disabled)
	// are exposed in the UI.
	const STATUS_TRANSITIONS: Record<string, { label: string; target: string }[]> = {
		draft: [{ label: 'Activate', target: 'active' }],
		active: [
			{ label: 'Disable', target: 'disabled' },
			{ label: 'Deprecate', target: 'deprecated' },
		],
		disabled: [
			{ label: 'Re-activate', target: 'active' },
			{ label: 'Deprecate', target: 'deprecated' },
		],
		deprecated: [],
		degraded: [
			{ label: 'Mark Active', target: 'active' },
			{ label: 'Disable', target: 'disabled' },
		],
	};

	async function transitionStatus(systemId: string, newStatus: string) {
		if (transitioning) return;
		transitioning = true;
		error = '';
		try {
			await apiJson(`/catalog/systems/${systemId}/status`, {
				method: 'PUT',
				body: JSON.stringify({ status: newStatus }),
			});
			await loadSystems();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Status transition failed';
		} finally {
			transitioning = false;
		}
	}

	function methodVariant(method: string): string {
		switch (method.toUpperCase()) {
			case 'GET':
				return 'bg-success/10 text-success';
			case 'POST':
				return 'bg-accent/10 text-accent';
			case 'PUT':
			case 'PATCH':
				return 'bg-warning/10 text-warning';
			case 'DELETE':
				return 'bg-danger/10 text-danger';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
		}
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">System Catalog</h1>
			<p class="text-sm text-text-secondary">Manage external systems and their endpoints</p>
		</div>
		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={() => showImportWizard = true}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover"
			>
				<FileUp size={16} />
				Import from OpenAPI
			</button>
			<button
				type="button"
				onclick={triggerDetectSystems}
				disabled={isDetecting}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50 disabled:cursor-not-allowed"
			>
				{#if isDetecting}
					<Loader2 size={16} class="animate-spin" />
					Detecting...
				{:else}
					<Sparkles size={16} />
					Detect Systems
				{/if}
			</button>
			<button
				type="button"
				onclick={openAddForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Add System
			</button>
		</div>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- System Wizard modal -->
	{#if showForm}
		<SystemWizard
			editingSystem={editingSystemFull}
			onClose={closeWizard}
			onSaved={onWizardSaved}
		/>
	{/if}

	<!-- Endpoint Wizard modal -->
	{#if showEndpointWizard}
		<EndpointWizard
			systemId={endpointWizardSystemId}
			editingEndpoint={editingEndpoint}
			onClose={closeEndpointWizard}
			onSaved={onEndpointSaved}
		/>
	{/if}

	<!-- OpenAPI Import Wizard modal -->
	{#if showImportWizard}
		<OpenAPIImportWizard
			onClose={() => showImportWizard = false}
			onImported={() => { showImportWizard = false; loadSystems(); }}
		/>
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
							<th class="w-8 px-4 py-2"></th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Name</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Base URL</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Status</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Tags</th>
							<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each systems as system, i}
							{@const expanded = expandedIds.has(system.id)}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2">
									<button
										type="button"
										onclick={() => toggleExpand(system.id)}
										class="text-text-secondary hover:text-text-primary"
									>
										{#if expanded}
											<ChevronDown size={14} />
										{:else}
											<ChevronRight size={14} />
										{/if}
									</button>
								</td>
								<td class="px-4 py-2 font-medium text-text-primary">{system.name}</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{system.base_url}
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-2">
										<span
											class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {statusVariant(system.status)}"
										>
											{system.status}
										</span>
										{#if STATUS_TRANSITIONS[system.status]?.length > 0}
											<div class="flex gap-1">
												{#each STATUS_TRANSITIONS[system.status] as action}
													{#if action.target === 'deprecated' && confirmingDeprecateId === system.id}
														<div class="flex items-center gap-1.5">
															<span class="text-xs text-danger">Deprecate?</span>
															<button
																type="button"
																onclick={() => { confirmingDeprecateId = null; transitionStatus(system.id, 'deprecated'); }}
																class="rounded px-1.5 py-0.5 text-xs font-medium text-danger hover:bg-danger/10"
																disabled={transitioning}
															>
																Yes
															</button>
															<button
																type="button"
																onclick={() => { confirmingDeprecateId = null; }}
																class="rounded px-1.5 py-0.5 text-xs text-text-secondary hover:bg-surface-hover"
															>
																No
															</button>
														</div>
													{:else if action.target === 'deprecated'}
														<button
															type="button"
															class="rounded px-2 py-0.5 text-xs text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
															onclick={() => { confirmingDeprecateId = system.id; }}
															title="{action.label} {system.name}"
															disabled={transitioning}
														>
															{action.label}
														</button>
													{:else}
														<button
															type="button"
															class="rounded px-2 py-0.5 text-xs text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
															onclick={() => transitionStatus(system.id, action.target)}
															title="{action.label} {system.name}"
															disabled={transitioning}
														>
															{action.label}
														</button>
													{/if}
												{/each}
											</div>
										{/if}
									</div>
								</td>
								<td class="px-4 py-2">
									{#if system.tags.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each system.tags as tag}
												<span
													class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
												>
													{tag}
												</span>
											{/each}
										</div>
									{:else}
										<span class="text-xs text-text-secondary">--</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									{#if confirmingDeleteId === system.id}
										<div class="flex items-center gap-1.5">
											<span class="text-xs text-danger">Delete?</span>
											<button
												type="button"
												onclick={() => confirmAndDelete(system.id)}
												class="rounded px-1.5 py-0.5 text-xs font-medium text-danger hover:bg-danger/10"
											>
												Yes
											</button>
											<button
												type="button"
												onclick={cancelDeleteConfirm}
												class="rounded px-1.5 py-0.5 text-xs text-text-secondary hover:bg-surface-hover"
											>
												No
											</button>
										</div>
									{:else}
										<div class="flex items-center gap-1">
											<button
												type="button"
												onclick={() => openEditForm(system)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
												title="Edit"
											>
												<Pencil size={14} />
											</button>
											<button
												type="button"
												onclick={() => startDelete(system.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										</div>
									{/if}
								</td>
							</tr>

							<!-- Expanded endpoints -->
							{#if expanded}
								<tr class="bg-surface-secondary/30">
									<td colspan="6" class="px-8 py-3">
										{#if endpointCache[system.id] && endpointCache[system.id].length > 0}
											<table class="w-full text-left text-xs">
												<thead>
													<tr class="border-b border-border">
														<th class="px-3 py-1.5 font-medium text-text-secondary">
															Method
														</th>
														<th class="px-3 py-1.5 font-medium text-text-secondary">
															Path
														</th>
														<th class="px-3 py-1.5 font-medium text-text-secondary">
															Description
														</th>
														<th class="px-3 py-1.5 font-medium text-text-secondary">
															Actions
														</th>
													</tr>
												</thead>
												<tbody>
													{#each endpointCache[system.id] as ep}
														<tr class="border-b border-border/50 last:border-b-0">
															<td class="px-3 py-1.5">
																<span class="rounded px-1.5 py-0.5 font-mono font-medium {methodVariant(ep.method)}">
																	{ep.method}
																</span>
																{#if ep.protocol_type && ep.protocol_type !== 'rest'}
																	<span class="ml-1 rounded bg-surface-secondary px-1 py-0.5 text-[10px] font-medium uppercase text-text-secondary">
																		{ep.protocol_type}
																	</span>
																{/if}
															</td>
															<td class="px-3 py-1.5 font-mono text-text-primary">
																{ep.path}
															</td>
															<td class="px-3 py-1.5 text-text-secondary">
																{ep.description}
															</td>
															<td class="px-3 py-1.5">
																<div class="flex items-center gap-1">
																	<button
																		type="button"
																		onclick={() => openEditEndpoint(ep)}
																		class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
																		title="Edit endpoint"
																	>
																		<Pencil size={12} />
																	</button>
																	<button
																		type="button"
																		onclick={() => deleteEndpoint(ep.id, system.id)}
																		class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
																		title="Delete endpoint"
																	>
																		<Trash2 size={12} />
																	</button>
																</div>
															</td>
														</tr>
													{/each}
												</tbody>
											</table>

											<div class="mt-2">
												<button
													type="button"
													onclick={() => openAddEndpoint(system.id)}
													class="inline-flex items-center gap-1 rounded-md border border-dashed border-border px-2.5 py-1 text-xs text-text-secondary transition-colors hover:border-accent hover:text-accent"
												>
													<Plus size={12} />
													Add Endpoint
												</button>
											</div>
										{:else}
											<p class="text-xs text-text-secondary">
												No endpoints configured for this system.
											</p>
											<div class="mt-2">
												<button
													type="button"
													onclick={() => openAddEndpoint(system.id)}
													class="inline-flex items-center gap-1 rounded-md border border-dashed border-border px-2.5 py-1 text-xs text-text-secondary transition-colors hover:border-accent hover:text-accent"
												>
													<Plus size={12} />
													Add Endpoint
												</button>
											</div>
										{/if}
									</td>
								</tr>
							{/if}
						{:else}
							<tr>
								<td colspan="6" class="px-4 py-8 text-center text-sm text-text-secondary">
									No systems in the catalog. Add one to get started.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- Detection log panel -->
	{#if showDetectionLog && detectionLog.length > 0}
		<div class="rounded-lg border border-border bg-surface">
			<div class="flex items-center justify-between border-b border-border px-4 py-2.5">
				<div class="flex items-center gap-2">
					<Sparkles size={16} class="text-accent" />
					<span class="text-sm font-medium text-text-primary">System Detection</span>
					{#if isDetecting}
						<span class="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
							<Loader2 size={10} class="animate-spin" />
							Running
						</span>
					{:else if detectJobStatus === 'completed'}
						<span class="rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
							Complete
						</span>
					{:else if detectJobStatus === 'failed'}
						<span class="rounded-full bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger">
							Failed
						</span>
					{/if}
				</div>
				<button
					type="button"
					onclick={() => { showDetectionLog = false; }}
					class="rounded p-1 text-text-secondary hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={14} />
				</button>
			</div>
			<div
				bind:this={detectionLogEl}
				class="max-h-64 overflow-y-auto px-4 py-3"
			>
				<div class="space-y-1">
					{#each detectionLog as entry, i}
						<div class="flex items-start gap-3 rounded px-2 py-1.5 text-sm hover:bg-surface-hover/50">
							<div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-secondary text-text-secondary">
								{#if entry.type === 'done'}
									<CheckCircle2 size={12} class="text-success" />
								{:else if entry.type === 'error'}
									<AlertCircle size={12} class="text-danger" />
								{:else}
									<Sparkles size={12} class="text-accent" />
								{/if}
							</div>
							<div class="min-w-0 flex-1">
								<p class="text-text-primary">{entry.message}</p>
								<p class="text-[10px] text-text-secondary/60">{entry.timestamp.toLocaleTimeString()} · {entry.pct}%</p>
							</div>
						</div>
					{/each}
					{#if isDetecting}
						<div class="flex items-center gap-3 px-2 py-1.5">
							<Loader2 size={12} class="animate-spin text-accent" />
							<span class="text-xs text-text-secondary">Processing...</span>
						</div>
					{/if}
				</div>
			</div>
			{#if isDetecting || detectJobStatus === 'completed'}
				<div class="border-t border-border px-4 py-2">
					<div class="h-1.5 w-full overflow-hidden rounded-full bg-surface-secondary">
						<div
							class="h-full rounded-full transition-all duration-500 {detectJobStatus === 'completed' ? 'bg-success' : detectJobStatus === 'failed' ? 'bg-danger' : 'bg-accent'}"
							style="width: {detectProgress}%"
						></div>
					</div>
					<div class="mt-1 flex justify-between text-[10px] text-text-secondary/60">
						<span>{detectJobStatus === 'completed' ? 'Detection complete' : 'Detecting...'}</span>
						<span>{detectProgress}%</span>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
