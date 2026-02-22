<!--
  LLMProviderManager.svelte - CRUD interface for LLM provider configuration.

  Lists providers in a table with inline forms for adding / editing.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Pencil,
		Trash2,
		X,
		Save,
		Loader2,
		Zap,
		Star,
		CheckCircle,
		XCircle
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface LLMProvider {
		id: string;
		name: string;
		provider_type: string;
		base_url: string | null;
		default_model: string | null;
		is_default: boolean;
		is_active: boolean;
		has_api_key: boolean;
		models: Array<{ id: string; name: string }>;
		capabilities: Record<string, boolean>;
		config: Record<string, unknown>;
	}

	interface HealthStatus {
		provider_id: string;
		name: string;
		reachable: boolean;
		latency_ms: number | null;
		error: string | null;
		checked_at: string;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const PROVIDER_TYPES = [
		{ value: 'openai', label: 'OpenAI' },
		{ value: 'anthropic', label: 'Anthropic' },
		{ value: 'google', label: 'Google' },
		{ value: 'azure_openai', label: 'Azure OpenAI' },
		{ value: 'ollama', label: 'Ollama' }
	];

	const DEFAULT_URLS: Record<string, string> = {
		openai: 'https://api.openai.com/v1',
		anthropic: 'https://api.anthropic.com/v1',
		google: 'https://generativelanguage.googleapis.com/v1beta',
		azure_openai: '',
		ollama: 'http://localhost:11434'
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providers = $state<LLMProvider[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let formData = $state({
		name: '',
		provider_type: 'openai',
		api_key: '',
		base_url: '',
		default_model: ''
	});
	let saving = $state(false);

	// Test connection state
	let testingId = $state<string | null>(null);
	let testResults = $state<Record<string, HealthStatus>>({});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadProviders() {
		loading = true;
		error = '';
		try {
			providers = await apiJson<LLMProvider[]>('/admin/llm-providers');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load providers';
		} finally {
			loading = false;
		}
	}

	// Initial load
	$effect(() => {
		loadProviders();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function openAddForm() {
		editingId = null;
		formData = {
			name: '',
			provider_type: 'openai',
			api_key: '',
			base_url: '',
			default_model: ''
		};
		showForm = true;
	}

	function openEditForm(provider: LLMProvider) {
		editingId = provider.id;
		formData = {
			name: provider.name,
			provider_type: provider.provider_type,
			api_key: '',
			base_url: provider.base_url || '',
			default_model: provider.default_model || ''
		};
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editingId = null;
	}

	async function submitForm() {
		saving = true;
		error = '';

		const payload: Record<string, unknown> = {
			name: formData.name,
			provider_type: formData.provider_type,
			base_url: formData.base_url || null,
			default_model: formData.default_model || null,
			models: [],
			capabilities: {},
			config: {}
		};

		// Only send api_key if user provided one
		if (formData.api_key) {
			payload.api_key = formData.api_key;
		}

		try {
			if (editingId) {
				payload.id = editingId;
				await apiJson(`/admin/llm-providers/${editingId}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				payload.id = crypto.randomUUID();
				await apiJson('/admin/llm-providers', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			showForm = false;
			editingId = null;
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save provider';
		} finally {
			saving = false;
		}
	}

	async function deleteProvider(id: string) {
		error = '';
		try {
			await apiFetch(`/admin/llm-providers/${id}`, { method: 'DELETE' });
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete provider';
		}
	}

	async function testConnection(provider: LLMProvider) {
		testingId = provider.id;
		try {
			const status = await apiJson<HealthStatus>(
				`/admin/llm-providers/${provider.id}/test`,
				{ method: 'POST' }
			);
			testResults = { ...testResults, [provider.id]: status };
		} catch (e) {
			testResults = {
				...testResults,
				[provider.id]: {
					provider_id: provider.id,
					name: provider.name,
					reachable: false,
					latency_ms: null,
					error: e instanceof Error ? e.message : 'Test failed',
					checked_at: new Date().toISOString()
				}
			};
		} finally {
			testingId = null;
		}
	}

	async function setDefault(id: string) {
		error = '';
		try {
			await apiJson(`/admin/llm-providers/${id}/default`, { method: 'PUT' });
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to set default provider';
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function providerLabel(type: string): string {
		return PROVIDER_TYPES.find((t) => t.value === type)?.label ?? type;
	}

	function defaultUrlHint(type: string): string {
		return DEFAULT_URLS[type] || '';
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">LLM Providers</h1>
			<p class="text-sm text-text-secondary">
				Manage language model providers and API keys
			</p>
		</div>
		<button
			type="button"
			onclick={openAddForm}
			class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			<Plus size={16} />
			Add Provider
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Inline form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">
					{editingId ? 'Edit Provider' : 'New Provider'}
				</h3>
				<button
					type="button"
					onclick={cancelForm}
					class="text-text-secondary hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<form
				onsubmit={(e) => {
					e.preventDefault();
					submitForm();
				}}
				class="grid grid-cols-2 gap-3"
			>
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Name</span>
					<input
						type="text"
						bind:value={formData.name}
						required
						placeholder="e.g. Production OpenAI"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Provider Type</span>
					<select
						bind:value={formData.provider_type}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						{#each PROVIDER_TYPES as pt}
							<option value={pt.value}>{pt.label}</option>
						{/each}
					</select>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						API Key
						{#if formData.provider_type === 'ollama'}
							<span class="text-text-secondary/60">(optional)</span>
						{/if}
					</span>
					<input
						type="password"
						bind:value={formData.api_key}
						placeholder={editingId ? 'Leave blank to keep existing' : 'sk-...'}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Base URL (optional)</span>
					<input
						type="text"
						bind:value={formData.base_url}
						placeholder={defaultUrlHint(formData.provider_type) || 'https://...'}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Default Model</span>
					<input
						type="text"
						bind:value={formData.default_model}
						placeholder="e.g. gpt-4o, claude-sonnet-4-20250514, gemini-pro"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<div class="col-span-2 flex justify-end gap-2 pt-1">
					<button
						type="button"
						onclick={cancelForm}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="submit"
						disabled={saving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						{editingId ? 'Update' : 'Create'}
					</button>
				</div>
			</form>
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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Name</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Base URL</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Default Model
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Default</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Active</th>
							<th class="w-48 px-4 py-2 text-xs font-medium text-text-secondary">
								Actions
							</th>
						</tr>
					</thead>
					<tbody>
						{#each providers as provider, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2 font-medium text-text-primary">
									{provider.name}
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										{providerLabel(provider.provider_type)}
									</span>
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{provider.base_url || '--'}
								</td>
								<td class="px-4 py-2 text-xs text-text-secondary">
									{provider.default_model || '--'}
								</td>
								<td class="px-4 py-2">
									{#if provider.is_default}
										<span
											class="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
										>
											<Star size={10} />
											Default
										</span>
									{:else}
										<span class="text-xs text-text-secondary">--</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									{#if provider.is_active}
										<span
											class="inline-block rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
										>
											Active
										</span>
									{:else}
										<span
											class="inline-block rounded-full bg-text-secondary/10 px-2 py-0.5 text-xs font-medium text-text-secondary"
										>
											Inactive
										</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={() => openEditForm(provider)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Edit"
										>
											<Pencil size={14} />
										</button>
										<button
											type="button"
											onclick={() => testConnection(provider)}
											disabled={testingId === provider.id}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent disabled:opacity-50"
											title="Test Connection"
										>
											{#if testingId === provider.id}
												<Loader2 size={14} class="animate-spin" />
											{:else}
												<Zap size={14} />
											{/if}
										</button>
										{#if !provider.is_default}
											<button
												type="button"
												onclick={() => setDefault(provider.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-success/10 hover:text-success"
												title="Set as Default"
											>
												<Star size={14} />
											</button>
										{/if}
										<button
											type="button"
											onclick={() => deleteProvider(provider.id)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
											title="Delete"
										>
											<Trash2 size={14} />
										</button>
									</div>

									<!-- Inline test result -->
									{#if testResults[provider.id]}
										{@const result = testResults[provider.id]}
										<div class="mt-1 text-xs">
											{#if result.reachable}
												<span
													class="inline-flex items-center gap-1 text-success"
												>
													<CheckCircle size={12} />
													Connected ({result.latency_ms}ms)
												</span>
											{:else}
												<span
													class="inline-flex items-center gap-1 text-danger"
												>
													<XCircle size={12} />
													{result.error || 'Unreachable'}
												</span>
											{/if}
										</div>
									{/if}
								</td>
							</tr>
						{:else}
							<tr>
								<td
									colspan="7"
									class="px-4 py-8 text-center text-sm text-text-secondary"
								>
									No LLM providers configured. Add one to get started.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
