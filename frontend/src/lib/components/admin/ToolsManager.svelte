<!--
  ToolsManager.svelte - Unified tool management for catalog, custom, and built-in tools.

  Merges tools from three sources into a single filterable list with
  expandable detail/edit panels. Catalog tools show read-only detail with
  test preview. Custom tools provide inline CRUD with code editor and
  test execution. Built-in tools are displayed read-only.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Wrench,
		ChevronDown,
		ChevronRight,
		Play,
		Loader2,
		Save,
		Plus,
		Trash2,
		X,
		ToggleLeft,
		ToggleRight,
		AlertTriangle,
		Code,
		Blocks,
		CheckCircle,
		XCircle
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import CodeEditor from '$lib/components/shared/CodeEditor.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface CatalogToolSummary {
		id: string;
		name: string;
		description: string;
		system_id?: string;
		method?: string;
		path?: string;
		risk_level?: string;
		required_permissions?: string[];
		enabled?: boolean;
	}

	interface CustomToolSummary {
		id: string;
		name: string;
		description: string;
		python_code?: string;
		parameters?: Record<string, unknown>;
		output_schema?: Record<string, unknown>;
		active?: boolean;
		source?: string;
		timeout_seconds?: number;
		max_memory_mb?: number;
		created_by?: string;
		created_at?: string;
		updated_at?: string;
	}

	interface UnifiedTool {
		id: string;
		name: string;
		description: string;
		type: 'catalog' | 'custom' | 'builtin';
		// Catalog fields
		system_id?: string;
		method?: string;
		path?: string;
		risk_level?: string;
		required_permissions?: string[];
		enabled?: boolean;
		// Custom / built-in fields
		python_code?: string;
		parameters?: Record<string, unknown>;
		output_schema?: Record<string, unknown>;
		active?: boolean;
		source?: string;
		timeout_seconds?: number;
		max_memory_mb?: number;
		created_by?: string;
		created_at?: string;
		updated_at?: string;
	}

	interface CatalogToolDetail {
		id: string;
		name: string;
		description: string;
		system_id: string;
		method: string;
		path: string;
		risk_level: string;
		required_permissions: string[];
		when_to_use: string;
		examples: string[];
		path_params: Record<string, unknown> | null;
		query_params: Record<string, unknown> | null;
		request_body: Record<string, unknown> | null;
		response_schema: Record<string, unknown> | null;
		timeout_seconds: number;
		tags: string[];
		enabled: boolean;
		config_overrides: Record<string, unknown>;
	}

	interface CatalogTestResult {
		endpoint_id: string;
		method: string;
		path: string;
		resolved_path: string;
		query_params: Record<string, unknown>;
		body: Record<string, unknown> | null;
		risk_level: string;
		would_require_permissions: string[];
		preview: boolean;
	}

	interface CustomTestResult {
		success: boolean;
		data: unknown;
		error: string | null;
	}

	type TabFilter = 'all' | 'catalog' | 'custom' | 'builtin';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let allTools = $state<UnifiedTool[]>([]);
	let loading = $state(true);
	let error = $state('');
	let activeTab = $state<TabFilter>('all');

	let filteredTools = $derived(
		activeTab === 'all' ? allTools : allTools.filter((t) => t.type === activeTab)
	);

	// Expanded detail
	let expandedId = $state<string | null>(null);
	let expandedToolType = $state<'catalog' | 'custom' | 'builtin' | null>(null);
	let detailLoading = $state(false);
	let catalogDetail = $state<CatalogToolDetail | null>(null);

	// Catalog test panel
	let catalogTestInput = $state('{}');
	let catalogTestLoading = $state(false);
	let catalogTestResult = $state<CatalogTestResult | null>(null);
	let catalogTestError = $state('');

	// Catalog config panel
	let configSaving = $state(false);
	let configPermissions = $state('');

	// Custom tool edit state
	let editName = $state('');
	let editDescription = $state('');
	let editPythonCode = $state('');
	let editParameters = $state('{}');
	let editActive = $state(true);
	let editSaving = $state(false);

	// Custom tool test state
	let customTestInput = $state('{}');
	let customTestLoading = $state(false);
	let customTestResult = $state<CustomTestResult | null>(null);
	let customTestError = $state('');

	// Custom tool delete state
	let confirmingDeleteId = $state<string | null>(null);
	let deleting = $state(false);

	// New custom tool creation
	let creatingNew = $state(false);
	let newName = $state('');
	let newDescription = $state('');
	let newPythonCode = $state('');
	let newParameters = $state('{}');
	let newSaving = $state(false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadAllTools() {
		loading = true;
		error = '';
		try {
			const [catalogTools, customTools] = await Promise.all([
				apiJson<CatalogToolSummary[]>('/admin/tools'),
				apiJson<CustomToolSummary[]>('/admin/custom-tools')
			]);

			const catalog: UnifiedTool[] = catalogTools.map((t) => ({
				...t,
				type: 'catalog' as const
			}));
			const custom: UnifiedTool[] = customTools.map((t) => ({
				...t,
				type: t.source === 'builtin' ? ('builtin' as const) : ('custom' as const)
			}));

			allTools = [...catalog, ...custom];
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load tools';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadAllTools();
	});

	// -----------------------------------------------------------------------
	// Expand / collapse
	// -----------------------------------------------------------------------

	function isEditDirty(tool: UnifiedTool): boolean {
		return (
			editName !== (tool.name ?? '') ||
			editDescription !== (tool.description ?? '') ||
			editPythonCode !== (tool.python_code ?? '') ||
			editActive !== (tool.active ?? true)
		);
	}

	async function toggleExpand(tool: UnifiedTool) {
		if (expandedId === tool.id) {
			expandedId = null;
			expandedToolType = null;
			catalogDetail = null;
			catalogTestResult = null;
			catalogTestError = '';
			customTestResult = null;
			customTestError = '';
			confirmingDeleteId = null;
			return;
		}

		// If switching from an edited custom tool, check for unsaved changes
		if (expandedId && expandedToolType === 'custom') {
			const current = allTools.find((t) => t.id === expandedId);
			if (current && isEditDirty(current)) {
				if (!confirm('You have unsaved changes. Discard them?')) {
					return;
				}
			}
		}

		expandedId = tool.id;
		expandedToolType = tool.type;
		catalogDetail = null;
		catalogTestResult = null;
		catalogTestError = '';
		catalogTestInput = '{}';
		customTestResult = null;
		customTestError = '';
		customTestInput = '{}';
		confirmingDeleteId = null;

		if (tool.type === 'catalog') {
			detailLoading = true;
			try {
				catalogDetail = await apiJson<CatalogToolDetail>(`/admin/tools/${tool.id}`);
				configPermissions = catalogDetail.required_permissions.join(', ');
			} catch (e) {
				error = e instanceof Error ? e.message : 'Failed to load tool detail';
			} finally {
				detailLoading = false;
			}
		} else {
			// Populate edit fields for custom tools
			editName = tool.name;
			editDescription = tool.description;
			editPythonCode = tool.python_code ?? '';
			editParameters = JSON.stringify(tool.parameters ?? {}, null, 2);
			editActive = tool.active ?? true;
		}
	}

	// -----------------------------------------------------------------------
	// Catalog tool actions
	// -----------------------------------------------------------------------

	async function runCatalogTest(endpointId: string) {
		catalogTestLoading = true;
		catalogTestError = '';
		catalogTestResult = null;
		try {
			let params: Record<string, unknown>;
			try {
				params = JSON.parse(catalogTestInput);
			} catch {
				catalogTestError = 'Invalid JSON in test input';
				return;
			}
			catalogTestResult = await apiJson<CatalogTestResult>(
				`/admin/tools/${endpointId}/test`,
				{
					method: 'POST',
					body: JSON.stringify({ params })
				}
			);
		} catch (e) {
			catalogTestError = e instanceof Error ? e.message : 'Test failed';
		} finally {
			catalogTestLoading = false;
		}
	}

	async function toggleCatalogEnabled(tool: UnifiedTool) {
		error = '';
		try {
			await apiJson(`/admin/tools/${tool.id}/config`, {
				method: 'PUT',
				body: JSON.stringify({ enabled: !tool.enabled })
			});
			await loadAllTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to toggle tool';
		}
	}

	async function saveCatalogConfig(endpointId: string) {
		configSaving = true;
		error = '';
		try {
			const permissions = configPermissions
				.split(',')
				.map((p) => p.trim())
				.filter(Boolean);
			await apiJson(`/admin/tools/${endpointId}/config`, {
				method: 'PUT',
				body: JSON.stringify({ required_permissions: permissions })
			});
			catalogDetail = await apiJson<CatalogToolDetail>(`/admin/tools/${endpointId}`);
			await loadAllTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save config';
		} finally {
			configSaving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Custom tool CRUD
	// -----------------------------------------------------------------------

	async function saveCustomTool(toolId: string) {
		editSaving = true;
		error = '';
		try {
			let parsedParams: Record<string, unknown> = {};
			try {
				parsedParams = JSON.parse(editParameters);
			} catch {
				error = 'Invalid JSON in parameters field';
				editSaving = false;
				return;
			}
			await apiJson(`/admin/custom-tools/${toolId}`, {
				method: 'PUT',
				body: JSON.stringify({
					name: editName,
					description: editDescription,
					python_code: editPythonCode,
					parameters: parsedParams,
					active: editActive
				})
			});
			await loadAllTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save custom tool';
		} finally {
			editSaving = false;
		}
	}

	async function deleteCustomTool(toolId: string) {
		deleting = true;
		error = '';
		try {
			await apiFetch(`/admin/custom-tools/${toolId}`, { method: 'DELETE' });
			expandedId = null;
			confirmingDeleteId = null;
			await loadAllTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete custom tool';
		} finally {
			deleting = false;
		}
	}

	async function runCustomTest(toolId: string) {
		customTestLoading = true;
		customTestError = '';
		customTestResult = null;
		try {
			let params: Record<string, unknown>;
			try {
				params = JSON.parse(customTestInput);
			} catch {
				customTestError = 'Invalid JSON in test input';
				return;
			}
			customTestResult = await apiJson<CustomTestResult>(
				`/admin/custom-tools/${toolId}/test`,
				{
					method: 'POST',
					body: JSON.stringify({ params })
				}
			);
		} catch (e) {
			customTestError = e instanceof Error ? e.message : 'Test failed';
		} finally {
			customTestLoading = false;
		}
	}

	// -----------------------------------------------------------------------
	// New custom tool creation
	// -----------------------------------------------------------------------

	function openNewToolForm() {
		creatingNew = true;
		newName = '';
		newDescription = '';
		newPythonCode = '';
		newParameters = '{}';
	}

	function cancelNewTool() {
		creatingNew = false;
	}

	async function createNewTool() {
		newSaving = true;
		error = '';
		try {
			let parsedParams: Record<string, unknown> = {};
			try {
				parsedParams = JSON.parse(newParameters);
			} catch {
				error = 'Invalid JSON in parameters field';
				newSaving = false;
				return;
			}
			await apiJson('/admin/custom-tools', {
				method: 'POST',
				body: JSON.stringify({
					name: newName,
					description: newDescription,
					python_code: newPythonCode,
					parameters: parsedParams,
					active: true
				})
			});
			creatingNew = false;
			await loadAllTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create custom tool';
		} finally {
			newSaving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	const riskColors: Record<string, string> = {
		read: 'bg-emerald-500/15 text-emerald-600',
		low_write: 'bg-yellow-500/15 text-yellow-600',
		high_write: 'bg-orange-500/15 text-orange-600',
		destructive: 'bg-red-500/15 text-red-600'
	};

	function riskBadgeClass(risk: string): string {
		return riskColors[risk] ?? 'bg-surface-secondary text-text-secondary';
	}

	function methodBadgeClass(method: string): string {
		const m = method.toUpperCase();
		if (m === 'GET') return 'bg-emerald-500/15 text-emerald-600';
		if (m === 'POST') return 'bg-blue-500/15 text-blue-600';
		if (m === 'PUT' || m === 'PATCH') return 'bg-yellow-500/15 text-yellow-600';
		if (m === 'DELETE') return 'bg-red-500/15 text-red-600';
		return 'bg-surface-secondary text-text-secondary';
	}

	function typeBadgeClass(type: 'catalog' | 'custom' | 'builtin'): string {
		if (type === 'catalog') return 'bg-blue-500/15 text-blue-600';
		if (type === 'custom') return 'bg-purple-500/15 text-purple-600';
		return 'bg-amber-500/15 text-amber-600';
	}

	function typeLabel(type: 'catalog' | 'custom' | 'builtin'): string {
		if (type === 'catalog') return 'Catalog';
		if (type === 'custom') return 'Custom';
		return 'Built-in';
	}

	const tabs: { id: TabFilter; label: string }[] = [
		{ id: 'all', label: 'All' },
		{ id: 'catalog', label: 'Catalog' },
		{ id: 'custom', label: 'Custom' },
		{ id: 'builtin', label: 'Built-in' }
	];

	let tabCounts = $derived({
		all: allTools.length,
		catalog: allTools.filter((t) => t.type === 'catalog').length,
		custom: allTools.filter((t) => t.type === 'custom').length,
		builtin: allTools.filter((t) => t.type === 'builtin').length
	});
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Tools Management</h1>
			<p class="text-sm text-text-secondary">
				Browse, test, and manage catalog, custom, and built-in tools
			</p>
		</div>
		<div class="flex items-center gap-3">
			<div class="flex items-center gap-2 text-sm text-text-secondary">
				<Wrench size={16} />
				{allTools.length} tool{allTools.length !== 1 ? 's' : ''}
			</div>
			<button
				type="button"
				onclick={openNewToolForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				New Custom Tool
			</button>
		</div>
	</div>

	<!-- Filter tabs -->
	<div class="flex gap-1 rounded-lg bg-surface-secondary p-1">
		{#each tabs as tab}
			<button
				type="button"
				class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors
					{activeTab === tab.id
					? 'bg-surface text-text-primary shadow-sm'
					: 'text-text-secondary hover:text-text-primary'}"
				onclick={() => (activeTab = tab.id)}
			>
				{tab.label}
				<span
					class="ml-1 inline-block rounded-full px-1.5 py-0.5 text-[10px] {activeTab === tab.id
						? 'bg-surface-secondary text-text-secondary'
						: 'bg-surface-secondary/50 text-text-secondary'}"
				>
					{tabCounts[tab.id]}
				</span>
			</button>
		{/each}
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- New custom tool form -->
	{#if creatingNew}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">New Custom Tool</h3>
				<button
					type="button"
					onclick={cancelNewTool}
					class="text-text-secondary hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<form
				onsubmit={(e) => {
					e.preventDefault();
					createNewTool();
				}}
				class="flex flex-col gap-3"
			>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Name</span>
						<input
							type="text"
							bind:value={newName}
							required
							placeholder="e.g. calculate_metrics"
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Description</span>
						<input
							type="text"
							bind:value={newDescription}
							required
							placeholder="What does this tool do?"
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>

				<div class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Python Code</span>
					<CodeEditor
						value={newPythonCode}
						language="python"
						placeholder={"async def run(params: dict) -> dict:\n    # Your tool logic here\n    return {\"result\"}"}
						onchange={(v) => (newPythonCode = v)}
					/>
				</div>

				<div class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Parameters (JSON Schema)</span>
					<CodeEditor
						value={newParameters}
						language="json"
						placeholder={'{"type": "object", "properties": {}}'}
						minHeight="120px"
						onchange={(v) => (newParameters = v)}
					/>
				</div>

				<div class="flex justify-end gap-2 pt-1">
					<button
						type="button"
						onclick={cancelNewTool}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="submit"
						disabled={newSaving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if newSaving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Plus size={14} />
						{/if}
						Create Tool
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- Tools list -->
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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Details</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Status</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredTools as tool, i}
							<!-- Summary row -->
							<tr
								class="border-b border-border last:border-b-0
									{i % 2 === 1 ? 'bg-surface-secondary/50' : ''}"
							>
								<td class="px-4 py-2">
									<button
										type="button"
										onclick={() => toggleExpand(tool)}
										class="text-text-secondary hover:text-text-primary"
									>
										{#if expandedId === tool.id}
											<ChevronDown size={14} />
										{:else}
											<ChevronRight size={14} />
										{/if}
									</button>
								</td>
								<td class="px-4 py-2">
									<div class="flex flex-col">
										<span class="font-medium text-text-primary">{tool.name}</span>
										<span class="text-xs text-text-secondary line-clamp-1">
											{tool.description}
										</span>
									</div>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {typeBadgeClass(tool.type)}"
									>
										{typeLabel(tool.type)}
									</span>
								</td>
								<td class="px-4 py-2">
									{#if tool.type === 'catalog'}
										<div class="flex items-center gap-2">
											{#if tool.method}
												<span
													class="inline-block rounded px-1.5 py-0.5 font-mono text-xs font-medium {methodBadgeClass(tool.method)}"
												>
													{tool.method}
												</span>
											{/if}
											{#if tool.path}
												<span class="max-w-[200px] truncate font-mono text-xs text-text-secondary">
													{tool.path}
												</span>
											{/if}
											{#if tool.risk_level}
												<span
													class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {riskBadgeClass(tool.risk_level)}"
												>
													{tool.risk_level}
												</span>
											{/if}
										</div>
									{:else if tool.type === 'custom'}
										<div class="flex items-center gap-2">
											<Code size={12} class="text-text-secondary" />
											<span class="text-xs text-text-secondary">Python</span>
											{#if tool.source === 'imported'}
												<span class="rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
													imported
												</span>
											{/if}
										</div>
									{:else}
										<div class="flex items-center gap-2">
											<Blocks size={12} class="text-text-secondary" />
											<span class="text-xs text-text-secondary">System built-in</span>
										</div>
									{/if}
								</td>
								<td class="px-4 py-2">
									{#if tool.type === 'catalog'}
										<button
											type="button"
											onclick={() => toggleCatalogEnabled(tool)}
											class="text-text-secondary transition-colors hover:text-text-primary"
											title={tool.enabled ? 'Disable' : 'Enable'}
										>
											{#if tool.enabled}
												<ToggleRight size={20} class="text-success" />
											{:else}
												<ToggleLeft size={20} />
											{/if}
										</button>
									{:else}
										{#if tool.active}
											<span class="inline-flex items-center gap-1 text-xs text-success">
												<CheckCircle size={12} />
												Active
											</span>
										{:else}
											<span class="inline-flex items-center gap-1 text-xs text-text-secondary">
												<XCircle size={12} />
												Inactive
											</span>
										{/if}
									{/if}
								</td>
							</tr>

							<!-- Expanded detail row -->
							{#if expandedId === tool.id}
								<tr class="border-b border-border last:border-b-0">
									<td colspan="5" class="px-6 py-4">
										<!-- ===== CATALOG TOOL DETAIL ===== -->
										{#if tool.type === 'catalog'}
											{#if detailLoading}
												<div class="flex items-center justify-center py-4">
													<Loader2 size={18} class="animate-spin text-text-secondary" />
												</div>
											{:else if catalogDetail}
												<div class="flex flex-col gap-4">
													<!-- Description & metadata -->
													<div class="grid grid-cols-2 gap-4">
														<div>
															<h4 class="mb-1 text-xs font-medium text-text-secondary">
																Description
															</h4>
															<p class="text-sm text-text-primary">
																{catalogDetail.description}
															</p>
														</div>
														<div>
															<h4 class="mb-1 text-xs font-medium text-text-secondary">
																When to Use
															</h4>
															<p class="text-sm text-text-primary">
																{catalogDetail.when_to_use}
															</p>
														</div>
													</div>

													<!-- System info -->
													<div class="flex items-center gap-4">
														<div>
															<h4 class="mb-1 text-xs font-medium text-text-secondary">
																System
															</h4>
															<span class="font-mono text-xs text-text-primary">
																{catalogDetail.system_id}
															</span>
														</div>
														<div>
															<h4 class="mb-1 text-xs font-medium text-text-secondary">
																Timeout
															</h4>
															<span class="text-xs text-text-primary">
																{catalogDetail.timeout_seconds}s
															</span>
														</div>
														{#if catalogDetail.tags.length > 0}
															<div>
																<h4 class="mb-1 text-xs font-medium text-text-secondary">
																	Tags
																</h4>
																<div class="flex flex-wrap gap-1">
																	{#each catalogDetail.tags as tag}
																		<span
																			class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
																		>
																			{tag}
																		</span>
																	{/each}
																</div>
															</div>
														{/if}
													</div>

													<!-- Parameters -->
													{#if catalogDetail.path_params || catalogDetail.query_params || catalogDetail.request_body}
														<div>
															<h4 class="mb-1 text-xs font-medium text-text-secondary">
																Parameters
															</h4>
															<div class="rounded-md border border-border bg-surface-secondary p-3">
																<pre
																	class="whitespace-pre-wrap font-mono text-xs text-text-primary"
																>{JSON.stringify(
																		{
																			path_params: catalogDetail.path_params,
																			query_params: catalogDetail.query_params,
																			request_body: catalogDetail.request_body
																		},
																		null,
																		2
																	)}</pre>
															</div>
														</div>
													{/if}

													<!-- Required permissions -->
													<div>
														<h4 class="mb-1 text-xs font-medium text-text-secondary">
															Required Permissions
														</h4>
														<div class="flex flex-wrap gap-1">
															{#each catalogDetail.required_permissions as perm}
																<span
																	class="inline-block rounded bg-surface-secondary px-2 py-0.5 font-mono text-xs text-text-secondary"
																>
																	{perm}
																</span>
															{:else}
																<span class="text-xs text-text-secondary">None</span>
															{/each}
														</div>
													</div>

													<!-- Test panel -->
													<div class="rounded-md border border-border p-3">
														<h4
															class="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-secondary"
														>
															<Play size={12} />
															Test Tool (Preview Mode)
														</h4>
														<div class="flex flex-col gap-2">
															<CodeEditor
																value={catalogTestInput}
																language="json"
																placeholder={'{"param_name": "value"}'}
																minHeight="120px"
																onchange={(v) => (catalogTestInput = v)}
															/>
															<div class="flex items-center gap-2">
																<button
																	type="button"
																	onclick={() => runCatalogTest(tool.id)}
																	disabled={catalogTestLoading}
																	class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
																>
																	{#if catalogTestLoading}
																		<Loader2 size={12} class="animate-spin" />
																	{:else}
																		<Play size={12} />
																	{/if}
																	Test
																</button>
																<span class="flex items-center gap-1 text-xs text-text-secondary">
																	<AlertTriangle size={12} />
																	Preview only -- no actual execution
																</span>
															</div>
														</div>

														{#if catalogTestError}
															<div
																class="mt-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger"
															>
																{catalogTestError}
															</div>
														{/if}

														{#if catalogTestResult}
															<div
																class="mt-2 rounded-md border border-border bg-surface-secondary p-3"
															>
																<pre
																	class="whitespace-pre-wrap font-mono text-xs text-text-primary"
																>{JSON.stringify(catalogTestResult, null, 2)}</pre>
															</div>
														{/if}
													</div>

													<!-- Config panel -->
													<div class="rounded-md border border-border p-3">
														<h4
															class="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-secondary"
														>
															<Wrench size={12} />
															Configuration Overrides
														</h4>
														<div class="flex flex-col gap-2">
															<label class="flex flex-col gap-1">
																<span class="text-xs text-text-secondary">
																	Custom required permissions (comma-separated)
																</span>
																<input
																	type="text"
																	bind:value={configPermissions}
																	placeholder="e.g. catalog:read, catalog:write"
																	class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
																/>
															</label>
															<div class="flex justify-end">
																<button
																	type="button"
																	onclick={() => saveCatalogConfig(tool.id)}
																	disabled={configSaving}
																	class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
																>
																	{#if configSaving}
																		<Loader2 size={12} class="animate-spin" />
																	{:else}
																		<Save size={12} />
																	{/if}
																	Save Config
																</button>
															</div>
														</div>
													</div>
												</div>
											{/if}

										<!-- ===== CUSTOM TOOL EDITOR ===== -->
										{:else if tool.type === 'custom'}
											<div class="flex flex-col gap-4">
												<div class="grid grid-cols-2 gap-3">
													<label class="flex flex-col gap-1">
														<span class="text-xs font-medium text-text-secondary">Name</span>
														<input
															type="text"
															bind:value={editName}
															class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
														/>
													</label>
													<label class="flex flex-col gap-1">
														<span class="text-xs font-medium text-text-secondary">
															Description
														</span>
														<input
															type="text"
															bind:value={editDescription}
															class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
														/>
													</label>
												</div>

												<div class="flex flex-col gap-1">
													<span class="text-xs font-medium text-text-secondary">
														Python Code
													</span>
													<CodeEditor
														value={editPythonCode}
														language="python"
														onchange={(v) => (editPythonCode = v)}
													/>
												</div>

												<div class="flex flex-col gap-1">
													<span class="text-xs font-medium text-text-secondary">
														Parameters (JSON)
													</span>
													<CodeEditor
														value={editParameters}
														language="json"
														minHeight="120px"
														onchange={(v) => (editParameters = v)}
													/>
												</div>

												<!-- Active toggle -->
												<div class="flex items-center gap-3">
													<label class="flex items-center gap-2 text-sm text-text-primary">
														<button
															type="button"
															onclick={() => (editActive = !editActive)}
															class="text-text-secondary transition-colors hover:text-text-primary"
														>
															{#if editActive}
																<ToggleRight size={24} class="text-success" />
															{:else}
																<ToggleLeft size={24} />
															{/if}
														</button>
														{editActive ? 'Active' : 'Inactive'}
													</label>
												</div>

												<!-- Action buttons -->
												<div class="flex items-center justify-between">
													<div class="flex items-center gap-2">
														{#if confirmingDeleteId === tool.id}
															<div class="flex items-center gap-1.5">
																<span class="text-xs text-danger">Delete this tool?</span>
																<button
																	type="button"
																	onclick={() => deleteCustomTool(tool.id)}
																	disabled={deleting}
																	class="rounded px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10"
																>
																	{#if deleting}
																		<Loader2 size={12} class="animate-spin" />
																	{:else}
																		Yes, Delete
																	{/if}
																</button>
																<button
																	type="button"
																	onclick={() => (confirmingDeleteId = null)}
																	class="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-hover"
																>
																	Cancel
																</button>
															</div>
														{:else}
															<button
																type="button"
																onclick={() => (confirmingDeleteId = tool.id)}
																class="inline-flex items-center gap-1.5 rounded-md border border-danger/30 px-3 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/5"
															>
																<Trash2 size={12} />
																Delete
															</button>
														{/if}
													</div>
													<div class="flex items-center gap-2">
														<button
															type="button"
															onclick={() => saveCustomTool(tool.id)}
															disabled={editSaving}
															class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
														>
															{#if editSaving}
																<Loader2 size={12} class="animate-spin" />
															{:else}
																<Save size={12} />
															{/if}
															Save Changes
														</button>
													</div>
												</div>

												<!-- Test panel -->
												<div class="rounded-md border border-border p-3">
													<h4
														class="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-secondary"
													>
														<Play size={12} />
														Test Tool
													</h4>
													<div class="flex flex-col gap-2">
														<CodeEditor
															value={customTestInput}
															language="json"
															placeholder={'{"param_name": "value"}'}
															minHeight="120px"
															onchange={(v) => (customTestInput = v)}
														/>
														<div class="flex items-center gap-2">
															<button
																type="button"
																onclick={() => runCustomTest(tool.id)}
																disabled={customTestLoading}
																class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
															>
																{#if customTestLoading}
																	<Loader2 size={12} class="animate-spin" />
																{:else}
																	<Play size={12} />
																{/if}
																Run Test
															</button>
														</div>
													</div>

													{#if customTestError}
														<div
															class="mt-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger"
														>
															{customTestError}
														</div>
													{/if}

													{#if customTestResult}
														<div
															class="mt-2 rounded-md border border-border bg-surface-secondary p-3"
														>
															<div class="mb-2 flex items-center gap-1.5">
																{#if customTestResult.success}
																	<CheckCircle size={14} class="text-success" />
																	<span class="text-xs font-medium text-success">
																		Success
																	</span>
																{:else}
																	<XCircle size={14} class="text-danger" />
																	<span class="text-xs font-medium text-danger">
																		Failed
																	</span>
																{/if}
															</div>
															{#if customTestResult.error}
																<p class="mb-2 text-xs text-danger">
																	{customTestResult.error}
																</p>
															{/if}
															{#if customTestResult.data !== undefined && customTestResult.data !== null}
																<pre
																	class="whitespace-pre-wrap font-mono text-xs text-text-primary"
																>{JSON.stringify(customTestResult.data, null, 2)}</pre>
															{/if}
														</div>
													{/if}
												</div>

												<!-- Metadata footer -->
												{#if tool.created_at || tool.created_by}
													<div class="flex items-center gap-4 border-t border-border pt-3 text-xs text-text-secondary">
														{#if tool.created_by}
															<span>Created by: {tool.created_by}</span>
														{/if}
														{#if tool.created_at}
															<span>
																Created: {new Date(tool.created_at).toLocaleDateString()}
															</span>
														{/if}
														{#if tool.updated_at}
															<span>
																Updated: {new Date(tool.updated_at).toLocaleDateString()}
															</span>
														{/if}
													</div>
												{/if}
											</div>

										<!-- ===== BUILT-IN TOOL (READ-ONLY) ===== -->
										{:else}
											<div class="flex flex-col gap-3">
												<div
													class="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-600"
												>
													<Blocks size={14} />
													Built-in tool -- cannot be modified or deleted
												</div>

												<div>
													<h4 class="mb-1 text-xs font-medium text-text-secondary">
														Name
													</h4>
													<p class="text-sm text-text-primary">{tool.name}</p>
												</div>

												<div>
													<h4 class="mb-1 text-xs font-medium text-text-secondary">
														Description
													</h4>
													<p class="text-sm text-text-primary">{tool.description}</p>
												</div>

												{#if tool.python_code}
													<div>
														<h4 class="mb-1 text-xs font-medium text-text-secondary">
															Source Code
														</h4>
														<CodeEditor
															value={tool.python_code}
															language="python"
															readonly={true}
														/>
													</div>
												{/if}

												{#if tool.parameters && Object.keys(tool.parameters).length > 0}
													<div>
														<h4 class="mb-1 text-xs font-medium text-text-secondary">
															Parameters
														</h4>
														<CodeEditor
															value={JSON.stringify(tool.parameters, null, 2)}
															language="json"
															readonly={true}
															minHeight="120px"
														/>
													</div>
												{/if}

												<div class="flex items-center gap-2 text-xs text-text-secondary">
													<span>
														Status: {tool.active ? 'Active' : 'Inactive'}
													</span>
													{#if tool.timeout_seconds}
														<span>Timeout: {tool.timeout_seconds}s</span>
													{/if}
												</div>
											</div>
										{/if}
									</td>
								</tr>
							{/if}
						{:else}
							<tr>
								<td colspan="5" class="px-4 py-8 text-center text-sm text-text-secondary">
									{#if activeTab === 'all'}
										No tools found. Register service endpoints in the Catalog or create custom tools.
									{:else if activeTab === 'catalog'}
										No catalog tools found. Register service endpoints in the System Catalog.
									{:else if activeTab === 'custom'}
										No custom tools found. Click "New Custom Tool" to create one.
									{:else}
										No built-in tools available.
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
