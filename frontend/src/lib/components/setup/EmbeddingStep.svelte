<!--
  EmbeddingStep.svelte -- Configure embedding provider & vector store.

  Presents embedding provider selection with model presets, vector store
  configuration, and a "Test Embedding" button that verifies the chosen
  provider via POST /api/setup/test-embedding (no auth required).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Loader2,
		CheckCircle,
		XCircle,
		ArrowLeft,
		ArrowRight,
		Eye,
		EyeOff
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface EmbeddingStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: EmbeddingStepProps = $props();

	// -----------------------------------------------------------------------
	// Embedding provider definitions with model presets
	// -----------------------------------------------------------------------

	interface ModelPreset {
		id: string;
		name: string;
		dimensions: number;
	}

	interface EmbeddingProviderDef {
		id: string;
		name: string;
		description: string;
		needsApiKey: boolean;
		needsBaseUrl: boolean;
		baseUrlPlaceholder?: string;
		models: ModelPreset[];
	}

	const embeddingProviders: EmbeddingProviderDef[] = [
		{
			id: 'openai',
			name: 'OpenAI',
			description: 'text-embedding-3 family',
			needsApiKey: true,
			needsBaseUrl: false,
			models: [
				{ id: 'text-embedding-3-small', name: 'text-embedding-3-small', dimensions: 1536 },
				{ id: 'text-embedding-3-large', name: 'text-embedding-3-large', dimensions: 3072 }
			]
		},
		{
			id: 'voyage',
			name: 'Voyage',
			description: 'Voyage AI embeddings',
			needsApiKey: true,
			needsBaseUrl: false,
			models: [
				{ id: 'voyage-3', name: 'voyage-3', dimensions: 1024 },
				{ id: 'voyage-3-lite', name: 'voyage-3-lite', dimensions: 512 }
			]
		},
		{
			id: 'google',
			name: 'Google',
			description: 'Gemini text embeddings',
			needsApiKey: true,
			needsBaseUrl: false,
			models: [
				{ id: 'text-embedding-004', name: 'text-embedding-004', dimensions: 768 }
			]
		},
		{
			id: 'ollama',
			name: 'Ollama',
			description: 'Local embedding models',
			needsApiKey: false,
			needsBaseUrl: true,
			baseUrlPlaceholder: 'http://localhost:11434',
			models: [
				{ id: 'nomic-embed-text', name: 'nomic-embed-text', dimensions: 768 },
				{ id: 'mxbai-embed-large', name: 'mxbai-embed-large', dimensions: 1024 }
			]
		}
	];

	// -----------------------------------------------------------------------
	// Vector store definitions
	// -----------------------------------------------------------------------

	interface VectorStoreDef {
		id: string;
		name: string;
		description: string;
	}

	const vectorStores: VectorStoreDef[] = [
		{ id: 'sqlite', name: 'SQLite', description: 'Built-in, no extra setup' },
		{ id: 'pgvector', name: 'pgvector', description: 'Uses the main PostgreSQL database' },
		{ id: 'chromadb', name: 'ChromaDB', description: 'Persistent or HTTP client' },
		{ id: 'pinecone', name: 'Pinecone', description: 'Managed vector database' }
	];

	// -----------------------------------------------------------------------
	// State -- Embedding
	// -----------------------------------------------------------------------

	let selectedProvider = $state<string | null>(null);
	let selectedModel = $state('');
	let apiKey = $state('');
	let baseUrl = $state('');
	let dimensions = $state(1536);
	let showKey = $state(false);

	// -----------------------------------------------------------------------
	// State -- Vector Store
	// -----------------------------------------------------------------------

	let selectedStore = $state('sqlite');
	let chromaPath = $state('');
	let chromaUrl = $state('');
	let pineconeApiKey = $state('');
	let pineconeIndexName = $state('');
	let pineconeEnvironment = $state('');
	let showPineconeKey = $state(false);

	// -----------------------------------------------------------------------
	// State -- Test & Navigation
	// -----------------------------------------------------------------------

	let testing = $state(false);
	let testResult = $state<'success' | 'failure' | null>(null);
	let testMessage = $state('');
	let testDimensions = $state(0);
	let testDuration = $state(0);
	let skipped = $state(false);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let currentProviderDef = $derived(
		embeddingProviders.find((p) => p.id === selectedProvider) ?? null
	);

	let canTest = $derived(
		selectedProvider !== null &&
			selectedModel.length > 0 &&
			(!currentProviderDef?.needsApiKey || apiKey.length > 0)
	);

	let canContinue = $derived(testResult === 'success' || skipped);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function selectProvider(id: string) {
		selectedProvider = id;
		const def = embeddingProviders.find((p) => p.id === id);
		const firstModel = def?.models[0];
		selectedModel = firstModel?.id ?? '';
		dimensions = firstModel?.dimensions ?? 1536;
		apiKey = '';
		baseUrl = '';
		showKey = false;
		testResult = null;
		testMessage = '';
		skipped = false;
	}

	function handleModelChange(event: Event) {
		const select = event.target as HTMLSelectElement;
		selectedModel = select.value;
		// Auto-fill dimensions from preset
		const preset = currentProviderDef?.models.find((m) => m.id === selectedModel);
		if (preset) {
			dimensions = preset.dimensions;
		}
	}

	async function testEmbedding() {
		if (!selectedProvider || !selectedModel) return;
		testing = true;
		testResult = null;
		testMessage = '';

		try {
			const body: Record<string, string | number> = {
				provider: selectedProvider,
				model: selectedModel,
				dimensions
			};
			if (apiKey) body.api_key = apiKey;
			if (baseUrl) body.base_url = baseUrl;

			const result = await apiJson<{
				success: boolean;
				dimensions: number;
				duration_ms: number;
				error?: string;
			}>('/setup/test-embedding', {
				method: 'POST',
				body: JSON.stringify(body)
			});

			if (result.success) {
				testResult = 'success';
				testDimensions = result.dimensions;
				testDuration = result.duration_ms;
				testMessage = `Embedding successful -- ${result.dimensions} dimensions in ${Math.round(result.duration_ms)}ms`;
			} else {
				testResult = 'failure';
				testMessage = result.error ?? 'Embedding test failed.';
			}
		} catch (e) {
			testResult = 'failure';
			testMessage = e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			testing = false;
		}
	}

	function handleSkip() {
		skipped = true;
		testResult = null;
	}

	function handleContinue() {
		onNext({
			embedding: skipped
				? null
				: {
						provider: selectedProvider,
						model: selectedModel,
						api_key: apiKey || null,
						base_url: baseUrl || null,
						dimensions
					},
			vector_store: {
				type: selectedStore,
				chroma_path: chromaPath || null,
				chroma_url: chromaUrl || null,
				pinecone_api_key: pineconeApiKey || null,
				pinecone_index_name: pineconeIndexName || null,
				pinecone_environment: pineconeEnvironment || null
			}
		});
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Embeddings &amp; Vector Store</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Configure how documents are embedded and stored for semantic search.
	</p>

	<!-- Scrollable content area for smaller viewports -->
	<div class="mt-4 flex-1 space-y-6 overflow-y-auto pr-1">
		<!-- ================================================================= -->
		<!-- Section A: Embedding Provider -->
		<!-- ================================================================= -->
		<section>
			<h3 class="mb-3 text-xs font-semibold tracking-wider text-text-secondary uppercase">
				Embedding Provider
			</h3>

			<!-- Provider cards -->
			<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
				{#each embeddingProviders as provider}
					<button
						type="button"
						onclick={() => selectProvider(provider.id)}
						class="rounded-lg border px-3 py-3 text-left transition-all
							{selectedProvider === provider.id
							? 'border-ember bg-ember/5 shadow-sm'
							: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
					>
						<span
							class="block text-sm font-medium {selectedProvider === provider.id
								? 'text-ember'
								: 'text-text-primary'}">{provider.name}</span
						>
						<span class="mt-0.5 block text-[11px] text-text-secondary"
							>{provider.description}</span
						>
					</button>
				{/each}
			</div>

			<!-- Provider configuration form -->
			{#if selectedProvider && currentProviderDef}
				<div class="mt-4 space-y-3">
					<!-- Model selection -->
					<div>
						<label
							for="embed-model-select"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							Model
						</label>
						<select
							id="embed-model-select"
							value={selectedModel}
							onchange={handleModelChange}
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
						>
							{#each currentProviderDef.models as model}
								<option value={model.id}>{model.name} ({model.dimensions}d)</option>
							{/each}
						</select>
					</div>

					<!-- Dimensions -->
					<div>
						<label
							for="embed-dimensions"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							Dimensions
						</label>
						<input
							id="embed-dimensions"
							type="number"
							bind:value={dimensions}
							min={1}
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
						/>
					</div>

					<!-- API Key -->
					{#if currentProviderDef.needsApiKey}
						<div>
							<label
								for="embed-api-key"
								class="mb-1.5 block text-xs font-medium text-text-secondary"
							>
								API Key
							</label>
							<div class="relative">
								<input
									id="embed-api-key"
									type={showKey ? 'text' : 'password'}
									bind:value={apiKey}
									placeholder="sk-..."
									autocomplete="off"
									class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
								/>
								<button
									type="button"
									onclick={() => (showKey = !showKey)}
									class="absolute top-1/2 right-2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
									aria-label={showKey ? 'Hide API key' : 'Show API key'}
								>
									{#if showKey}
										<EyeOff size={16} />
									{:else}
										<Eye size={16} />
									{/if}
								</button>
							</div>
						</div>
					{/if}

					<!-- Base URL -->
					{#if currentProviderDef.needsBaseUrl}
						<div>
							<label
								for="embed-base-url"
								class="mb-1.5 block text-xs font-medium text-text-secondary"
							>
								Base URL
							</label>
							<input
								id="embed-base-url"
								type="url"
								bind:value={baseUrl}
								placeholder={currentProviderDef.baseUrlPlaceholder ?? 'https://...'}
								class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
							/>
						</div>
					{/if}

					<!-- Test Embedding button -->
					<button
						type="button"
						onclick={testEmbedding}
						disabled={testing || !canTest}
						class="btn-hover inline-flex items-center gap-2 rounded-lg bg-ember px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
					>
						{#if testing}
							<Loader2 size={16} class="animate-spin" />
							Testing...
						{:else}
							Test Embedding
						{/if}
					</button>

					<!-- Test result -->
					{#if testResult === 'success'}
						<div
							class="flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 px-4 py-3 text-sm text-success"
						>
							<CheckCircle size={18} class="mt-0.5 shrink-0" />
							<span>{testMessage}</span>
						</div>
					{:else if testResult === 'failure'}
						<div
							class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
						>
							<XCircle size={18} class="mt-0.5 shrink-0" />
							<span>{testMessage}</span>
						</div>
					{/if}
				</div>
			{/if}
		</section>

		<!-- ================================================================= -->
		<!-- Section B: Vector Store -->
		<!-- ================================================================= -->
		<section>
			<h3 class="mb-3 text-xs font-semibold tracking-wider text-text-secondary uppercase">
				Vector Store
			</h3>

			<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
				{#each vectorStores as store}
					<button
						type="button"
						onclick={() => (selectedStore = store.id)}
						class="rounded-lg border px-3 py-3 text-left transition-all
							{selectedStore === store.id
							? 'border-ember bg-ember/5 shadow-sm'
							: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
					>
						<span
							class="block text-sm font-medium {selectedStore === store.id
								? 'text-ember'
								: 'text-text-primary'}">{store.name}</span
						>
						<span class="mt-0.5 block text-[11px] text-text-secondary"
							>{store.description}</span
						>
					</button>
				{/each}
			</div>

			<!-- Vector store config fields -->
			{#if selectedStore === 'pgvector'}
				<p class="mt-3 text-xs text-text-secondary">
					pgvector will use the main PostgreSQL database connection. Make sure the
					<code class="rounded bg-surface-hover px-1 py-0.5 text-[11px]">vector</code>
					extension is enabled.
				</p>
			{:else if selectedStore === 'chromadb'}
				<div class="mt-3 space-y-3">
					<div>
						<label
							for="chroma-path"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							Persistent Path <span class="text-text-secondary/60">(local storage)</span>
						</label>
						<input
							id="chroma-path"
							type="text"
							bind:value={chromaPath}
							placeholder="./chroma_data"
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
						/>
					</div>
					<div>
						<label
							for="chroma-url"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							HTTP URL <span class="text-text-secondary/60">(remote server)</span>
						</label>
						<input
							id="chroma-url"
							type="url"
							bind:value={chromaUrl}
							placeholder="http://localhost:8000"
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
						/>
					</div>
					<p class="text-[11px] text-text-secondary">
						Provide either a local path or a remote URL. If both are set, the URL takes
						precedence.
					</p>
				</div>
			{:else if selectedStore === 'pinecone'}
				<div class="mt-3 space-y-3">
					<div>
						<label
							for="pinecone-api-key"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							API Key
						</label>
						<div class="relative">
							<input
								id="pinecone-api-key"
								type={showPineconeKey ? 'text' : 'password'}
								bind:value={pineconeApiKey}
								placeholder="pcsk_..."
								autocomplete="off"
								class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
							/>
							<button
								type="button"
								onclick={() => (showPineconeKey = !showPineconeKey)}
								class="absolute top-1/2 right-2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
								aria-label={showPineconeKey ? 'Hide API key' : 'Show API key'}
							>
								{#if showPineconeKey}
									<EyeOff size={16} />
								{:else}
									<Eye size={16} />
								{/if}
							</button>
						</div>
					</div>
					<div>
						<label
							for="pinecone-index"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							Index Name
						</label>
						<input
							id="pinecone-index"
							type="text"
							bind:value={pineconeIndexName}
							placeholder="firefly-desk"
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
						/>
					</div>
					<div>
						<label
							for="pinecone-env"
							class="mb-1.5 block text-xs font-medium text-text-secondary"
						>
							Environment
						</label>
						<input
							id="pinecone-env"
							type="text"
							bind:value={pineconeEnvironment}
							placeholder="us-east-1"
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
						/>
					</div>
				</div>
			{/if}
		</section>
	</div>

	<!-- Skip option -->
	{#if !canContinue}
		<div class="mt-4">
			<button
				type="button"
				onclick={handleSkip}
				class="text-sm text-text-secondary underline decoration-dotted underline-offset-4 hover:text-text-primary"
			>
				Skip for now
			</button>
		</div>
	{/if}

	{#if skipped && !testResult}
		<p class="mt-2 text-xs text-text-secondary">
			You can configure embeddings later in Admin &gt; Settings.
		</p>
	{/if}

	<!-- Navigation -->
	<div class="mt-6 flex items-center justify-between border-t border-border pt-4">
		<button
			type="button"
			onclick={onBack}
			class="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			<ArrowLeft size={16} />
			Back
		</button>
		<button
			type="button"
			onclick={handleContinue}
			disabled={!canContinue}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
		>
			Continue
			<ArrowRight size={16} />
		</button>
	</div>
</div>
