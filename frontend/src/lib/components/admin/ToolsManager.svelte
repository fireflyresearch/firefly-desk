<!--
  ToolsManager.svelte - Browse, test, and configure tool access.

  Lists all service endpoints (tools) in a table with expandable detail rows
  for description, parameters, test panel, and config overrides. Risk level
  badges are color-coded and tools can be enabled/disabled with permission
  overrides.

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
		ToggleLeft,
		ToggleRight,
		AlertTriangle
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface ToolSummary {
		id: string;
		name: string;
		description: string;
		system_id: string;
		method: string;
		path: string;
		risk_level: string;
		required_permissions: string[];
		enabled: boolean;
	}

	interface ToolDetail {
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

	interface ToolTestResult {
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

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let tools = $state<ToolSummary[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Expanded detail
	let expandedId = $state<string | null>(null);
	let detailLoading = $state(false);
	let detailData = $state<ToolDetail | null>(null);

	// Test panel
	let testInput = $state('{}');
	let testLoading = $state(false);
	let testResult = $state<ToolTestResult | null>(null);
	let testError = $state('');

	// Config panel
	let configSaving = $state(false);
	let configPermissions = $state('');

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadTools() {
		loading = true;
		error = '';
		try {
			tools = await apiJson<ToolSummary[]>('/admin/tools');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load tools';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadTools();
	});

	// -----------------------------------------------------------------------
	// Expand / collapse
	// -----------------------------------------------------------------------

	async function toggleExpand(toolId: string) {
		if (expandedId === toolId) {
			expandedId = null;
			detailData = null;
			testResult = null;
			testError = '';
			return;
		}
		expandedId = toolId;
		detailData = null;
		testResult = null;
		testError = '';
		testInput = '{}';
		detailLoading = true;
		try {
			detailData = await apiJson<ToolDetail>(`/admin/tools/${toolId}`);
			configPermissions = detailData.required_permissions.join(', ');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load tool detail';
		} finally {
			detailLoading = false;
		}
	}

	// -----------------------------------------------------------------------
	// Test tool
	// -----------------------------------------------------------------------

	async function runTest(endpointId: string) {
		testLoading = true;
		testError = '';
		testResult = null;
		try {
			const params = JSON.parse(testInput);
			testResult = await apiJson<ToolTestResult>(`/admin/tools/${endpointId}/test`, {
				method: 'POST',
				body: JSON.stringify({ params })
			});
		} catch (e) {
			testError = e instanceof Error ? e.message : 'Test failed';
		} finally {
			testLoading = false;
		}
	}

	// -----------------------------------------------------------------------
	// Config update
	// -----------------------------------------------------------------------

	async function toggleEnabled(tool: ToolSummary) {
		error = '';
		try {
			await apiJson(`/admin/tools/${tool.id}/config`, {
				method: 'PUT',
				body: JSON.stringify({ enabled: !tool.enabled })
			});
			await loadTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to toggle tool';
		}
	}

	async function saveConfig(endpointId: string) {
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
			// Reload detail
			detailData = await apiJson<ToolDetail>(`/admin/tools/${endpointId}`);
			await loadTools();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save config';
		} finally {
			configSaving = false;
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
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Tools Management</h1>
			<p class="text-sm text-text-secondary">
				Browse, test, and configure tool access for the agent
			</p>
		</div>
		<div class="flex items-center gap-2 text-sm text-text-secondary">
			<Wrench size={16} />
			{tools.length} tool{tools.length !== 1 ? 's' : ''} registered
		</div>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Tools table -->
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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">System</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Risk Level</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Method</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Path</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Enabled</th>
						</tr>
					</thead>
					<tbody>
						{#each tools as tool, i}
							<!-- Summary row -->
							<tr
								class="cursor-pointer border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover
									{i % 2 === 1 ? 'bg-surface-secondary/50' : ''}"
								onclick={() => toggleExpand(tool.id)}
							>
								<td class="px-4 py-2 text-text-secondary">
									{#if expandedId === tool.id}
										<ChevronDown size={14} />
									{:else}
										<ChevronRight size={14} />
									{/if}
								</td>
								<td class="px-4 py-2 font-medium text-text-primary">
									{tool.name}
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{tool.system_id}
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {riskBadgeClass(tool.risk_level)}"
									>
										{tool.risk_level}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded px-1.5 py-0.5 font-mono text-xs font-medium {methodBadgeClass(tool.method)}"
									>
										{tool.method}
									</span>
								</td>
								<td class="max-w-xs truncate px-4 py-2 font-mono text-xs text-text-secondary">
									{tool.path}
								</td>
								<td class="px-4 py-2">
									<button
										type="button"
										onclick={(e) => {
											e.stopPropagation();
											toggleEnabled(tool);
										}}
										class="text-text-secondary transition-colors hover:text-text-primary"
										title={tool.enabled ? 'Disable' : 'Enable'}
									>
										{#if tool.enabled}
											<ToggleRight size={20} class="text-success" />
										{:else}
											<ToggleLeft size={20} />
										{/if}
									</button>
								</td>
							</tr>

							<!-- Expanded detail row -->
							{#if expandedId === tool.id}
								<tr class="border-b border-border last:border-b-0">
									<td colspan="7" class="px-6 py-4">
										{#if detailLoading}
											<div class="flex items-center justify-center py-4">
												<Loader2 size={18} class="animate-spin text-text-secondary" />
											</div>
										{:else if detailData}
											<div class="flex flex-col gap-4">
												<!-- Description & metadata -->
												<div class="grid grid-cols-2 gap-4">
													<div>
														<h4 class="mb-1 text-xs font-medium text-text-secondary">
															Description
														</h4>
														<p class="text-sm text-text-primary">
															{detailData.description}
														</p>
													</div>
													<div>
														<h4 class="mb-1 text-xs font-medium text-text-secondary">
															When to Use
														</h4>
														<p class="text-sm text-text-primary">
															{detailData.when_to_use}
														</p>
													</div>
												</div>

												<!-- Parameters -->
												{#if detailData.path_params || detailData.query_params || detailData.request_body}
													<div>
														<h4 class="mb-1 text-xs font-medium text-text-secondary">
															Parameters
														</h4>
														<div class="rounded-md border border-border bg-surface-secondary p-3">
															<pre
																class="whitespace-pre-wrap font-mono text-xs text-text-primary"
															>{JSON.stringify(
																	{
																		path_params: detailData.path_params,
																		query_params: detailData.query_params,
																		request_body: detailData.request_body
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
														{#each detailData.required_permissions as perm}
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
														<textarea
															bind:value={testInput}
															rows={4}
															placeholder={'{"param_name": "value"}'}
															class="w-full rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-text-primary outline-none focus:border-accent"
														></textarea>
														<div class="flex items-center gap-2">
															<button
																type="button"
																onclick={() => runTest(tool.id)}
																disabled={testLoading}
																class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
															>
																{#if testLoading}
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

													{#if testError}
														<div
															class="mt-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger"
														>
															{testError}
														</div>
													{/if}

													{#if testResult}
														<div
															class="mt-2 rounded-md border border-border bg-surface-secondary p-3"
														>
															<pre
																class="whitespace-pre-wrap font-mono text-xs text-text-primary"
															>{JSON.stringify(testResult, null, 2)}</pre>
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
																onclick={() => saveConfig(tool.id)}
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
									</td>
								</tr>
							{/if}
						{:else}
							<tr>
								<td colspan="7" class="px-4 py-8 text-center text-sm text-text-secondary">
									No tools found. Register service endpoints in the Catalog to see them here.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
