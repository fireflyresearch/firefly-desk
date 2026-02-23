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
		XCircle,
		Cpu,
		ChevronDown,
		ChevronUp
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

	// Embedding configuration state
	interface EmbeddingConfig {
		embedding_model: string;
		embedding_api_key: string;
		embedding_base_url: string;
		embedding_dimensions: number;
	}

	interface EmbeddingTestResult {
		success: boolean;
		provider: string;
		model: string;
		dimensions: number;
		sample_vector_length: number | null;
		error: string | null;
	}

	const EMBEDDING_PROVIDERS = [
		{ value: 'openai', label: 'OpenAI' },
		{ value: 'voyage', label: 'Voyage AI' },
		{ value: 'google', label: 'Google' },
		{ value: 'ollama', label: 'Ollama' },
		{ value: 'azure', label: 'Azure OpenAI' }
	];

	const EMBEDDING_MODELS: Record<string, Array<{ value: string; label: string; dims: number }>> = {
		openai: [
			{ value: 'text-embedding-3-small', label: 'text-embedding-3-small', dims: 1536 },
			{ value: 'text-embedding-3-large', label: 'text-embedding-3-large', dims: 3072 },
			{ value: 'text-embedding-ada-002', label: 'text-embedding-ada-002', dims: 1536 }
		],
		voyage: [
			{ value: 'voyage-3.5', label: 'voyage-3.5', dims: 1024 },
			{ value: 'voyage-3', label: 'voyage-3', dims: 1024 },
			{ value: 'voyage-code-3', label: 'voyage-code-3', dims: 1024 }
		],
		google: [{ value: 'text-embedding-004', label: 'text-embedding-004', dims: 768 }],
		ollama: [
			{ value: 'nomic-embed-text', label: 'nomic-embed-text', dims: 768 },
			{ value: 'mxbai-embed-large', label: 'mxbai-embed-large', dims: 1024 }
		],
		azure: [
			{ value: 'text-embedding-3-small', label: 'text-embedding-3-small', dims: 1536 },
			{ value: 'text-embedding-3-large', label: 'text-embedding-3-large', dims: 3072 }
		]
	};

	let embeddingExpanded = $state(false);
	let embeddingConfig = $state<EmbeddingConfig | null>(null);
	let embeddingLoading = $state(false);
	let embeddingSaving = $state(false);
	let embeddingTesting = $state(false);
	let embeddingTestResult = $state<EmbeddingTestResult | null>(null);
	let embeddingError = $state('');

	// Derived embedding form state
	let embProvider = $state('openai');
	let embModel = $state('text-embedding-3-small');
	let embApiKey = $state('');
	let embBaseUrl = $state('');
	let embDimensions = $state(1536);

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
		loadEmbeddingConfig();
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
	// Embedding config actions
	// -----------------------------------------------------------------------

	async function loadEmbeddingConfig() {
		embeddingLoading = true;
		embeddingError = '';
		try {
			embeddingConfig = await apiJson<EmbeddingConfig>('/settings/embedding');
			if (embeddingConfig) {
				const parts = embeddingConfig.embedding_model.split(':', 2);
				embProvider = parts[0] || 'openai';
				embModel = parts[1] || 'text-embedding-3-small';
				embApiKey = embeddingConfig.embedding_api_key || '';
				embBaseUrl = embeddingConfig.embedding_base_url || '';
				embDimensions = embeddingConfig.embedding_dimensions || 1536;
			}
		} catch (e) {
			embeddingError =
				e instanceof Error ? e.message : 'Failed to load embedding configuration';
		} finally {
			embeddingLoading = false;
		}
	}

	function handleEmbProviderChange() {
		// Auto-select first model and dimensions for the selected provider
		const models = EMBEDDING_MODELS[embProvider];
		if (models && models.length > 0) {
			embModel = models[0].value;
			embDimensions = models[0].dims;
		}
	}

	function handleEmbModelChange() {
		// Auto-update dimensions when model changes
		const models = EMBEDDING_MODELS[embProvider];
		const selected = models?.find((m) => m.value === embModel);
		if (selected) {
			embDimensions = selected.dims;
		}
	}

	async function saveEmbeddingConfig() {
		embeddingSaving = true;
		embeddingError = '';
		embeddingTestResult = null;
		try {
			await apiJson<EmbeddingConfig>('/settings/embedding', {
				method: 'PUT',
				body: JSON.stringify({
					embedding_model: `${embProvider}:${embModel}`,
					embedding_api_key: embApiKey,
					embedding_base_url: embBaseUrl,
					embedding_dimensions: embDimensions
				})
			});
			await loadEmbeddingConfig();
		} catch (e) {
			embeddingError =
				e instanceof Error ? e.message : 'Failed to save embedding configuration';
		} finally {
			embeddingSaving = false;
		}
	}

	async function testEmbedding() {
		embeddingTesting = true;
		embeddingTestResult = null;
		embeddingError = '';
		try {
			embeddingTestResult = await apiJson<EmbeddingTestResult>('/settings/embedding/test', {
				method: 'POST'
			});
		} catch (e) {
			embeddingError =
				e instanceof Error ? e.message : 'Embedding test failed';
		} finally {
			embeddingTesting = false;
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

	<!-- Embedding Configuration Section -->
	<div class="rounded-lg border border-border bg-surface">
		<button
			type="button"
			onclick={() => (embeddingExpanded = !embeddingExpanded)}
			class="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-surface-hover"
		>
			<div class="flex items-center gap-2">
				<Cpu size={16} class="text-accent" />
				<span class="text-sm font-semibold text-text-primary">Embedding Configuration</span>
				<span class="text-xs text-text-secondary">
					{embeddingConfig
						? embeddingConfig.embedding_model
						: 'Not configured'}
				</span>
			</div>
			{#if embeddingExpanded}
				<ChevronUp size={16} class="text-text-secondary" />
			{:else}
				<ChevronDown size={16} class="text-text-secondary" />
			{/if}
		</button>

		{#if embeddingExpanded}
			<div class="border-t border-border px-4 py-4">
				<p class="mb-3 text-xs text-text-secondary">
					Embeddings power semantic search in the knowledge base. Configure a provider
					and model to enable vector-based retrieval. Without embeddings, keyword search
					is used as a fallback.
				</p>

				{#if embeddingError}
					<div
						class="mb-3 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger"
					>
						{embeddingError}
					</div>
				{/if}

				{#if embeddingLoading}
					<div class="flex items-center justify-center py-6">
						<Loader2 size={20} class="animate-spin text-text-secondary" />
					</div>
				{:else}
					<form
						onsubmit={(e) => {
							e.preventDefault();
							saveEmbeddingConfig();
						}}
						class="grid grid-cols-2 gap-3"
					>
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Provider</span>
							<select
								bind:value={embProvider}
								onchange={handleEmbProviderChange}
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							>
								{#each EMBEDDING_PROVIDERS as ep}
									<option value={ep.value}>{ep.label}</option>
								{/each}
							</select>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Model</span>
							<select
								bind:value={embModel}
								onchange={handleEmbModelChange}
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							>
								{#each EMBEDDING_MODELS[embProvider] || [] as m}
									<option value={m.value}>{m.label} ({m.dims}d)</option>
								{/each}
							</select>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">
								API Key
								{#if embProvider === 'ollama'}
									<span class="text-text-secondary/60">(not needed)</span>
								{/if}
							</span>
							<input
								type="password"
								bind:value={embApiKey}
								placeholder={embApiKey?.startsWith('***')
									? 'Leave blank to keep existing'
									: 'sk-...'}
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary"
								>Dimensions</span
							>
							<input
								type="number"
								bind:value={embDimensions}
								min="64"
								max="4096"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="col-span-2 flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary"
								>Base URL (optional)</span
							>
							<input
								type="text"
								bind:value={embBaseUrl}
								placeholder="Leave blank for default provider URL"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<div class="col-span-2 flex items-center justify-between pt-1">
							<!-- Test result -->
							<div class="text-xs">
								{#if embeddingTestResult}
									{#if embeddingTestResult.success}
										<span
											class="inline-flex items-center gap-1 text-success"
										>
											<CheckCircle size={12} />
											Connected (vector size: {embeddingTestResult.sample_vector_length})
										</span>
									{:else}
										<span
											class="inline-flex items-center gap-1 text-danger"
										>
											<XCircle size={12} />
											{embeddingTestResult.error || 'Test failed'}
										</span>
									{/if}
								{/if}
							</div>

							<div class="flex gap-2">
								<button
									type="button"
									onclick={testEmbedding}
									disabled={embeddingTesting}
									class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
								>
									{#if embeddingTesting}
										<Loader2 size={14} class="animate-spin" />
									{:else}
										<Zap size={14} />
									{/if}
									Test
								</button>
								<button
									type="submit"
									disabled={embeddingSaving}
									class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
								>
									{#if embeddingSaving}
										<Loader2 size={14} class="animate-spin" />
									{:else}
										<Save size={14} />
									{/if}
									Save
								</button>
							</div>
						</div>
					</form>
				{/if}
			</div>
		{/if}
	</div>
</div>
