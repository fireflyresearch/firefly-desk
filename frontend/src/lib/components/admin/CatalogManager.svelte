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
		Loader2
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import SystemWizard from './SystemWizard.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Endpoint {
		id: string;
		system_id: string;
		method: string;
		path: string;
		description: string;
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

	// Wizard state
	let showForm = $state(false);
	let saving = $state(false);
	let editingSystemFull = $state<SystemFull | null>(null);

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
	// Helpers
	// -----------------------------------------------------------------------

	let confirmingDeleteId = $state<string | null>(null);

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
			case 'inactive':
				return 'bg-text-secondary/10 text-text-secondary';
			case 'error':
				return 'bg-danger/10 text-danger';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
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
		<button
			type="button"
			onclick={openAddForm}
			class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			<Plus size={16} />
			Add System
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
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
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {statusVariant(system.status)}"
									>
										{system.status}
									</span>
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
													</tr>
												</thead>
												<tbody>
													{#each endpointCache[system.id] as ep}
														<tr class="border-b border-border/50 last:border-b-0">
															<td class="px-3 py-1.5">
																<span class="rounded px-1.5 py-0.5 font-mono font-medium {methodVariant(ep.method)}">
																	{ep.method}
																</span>
															</td>
															<td class="px-3 py-1.5 font-mono text-text-primary">
																{ep.path}
															</td>
															<td class="px-3 py-1.5 text-text-secondary">
																{ep.description}
															</td>
														</tr>
													{/each}
												</tbody>
											</table>
										{:else}
											<p class="text-xs text-text-secondary">
												No endpoints configured for this system.
											</p>
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
</div>
