<!--
  AdminSettings.svelte - Platform-wide configuration panel.

  Centralises search engine, branding, and knowledge quality settings
  that were previously scattered across other admin views.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Palette,
		BookOpen,
		Loader2,
		CheckCircle,
		AlertTriangle,
		XCircle,
		Save,
		Globe,
		TestTube
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Search engine state
	// -----------------------------------------------------------------------

	let searchProvider = $state('');
	let searchApiKey = $state('');
	let searchMaxResults = $state(5);
	let searchLoading = $state(true);
	let searchSaving = $state(false);
	let searchTesting = $state(false);
	let searchTestResult = $state<{
		success: boolean;
		error?: string;
		result_count?: number;
	} | null>(null);

	// -----------------------------------------------------------------------
	// Branding state
	// -----------------------------------------------------------------------

	let appTitle = $state('Firefly Desk');
	let accentColor = $state('#2563EB');
	let brandingLoading = $state(true);
	let brandingSaving = $state(false);
	let brandingSaved = $state(false);

	// -----------------------------------------------------------------------
	// Knowledge quality state
	// -----------------------------------------------------------------------

	let chunkingMode = $state<'auto' | 'structural' | 'fixed'>('auto');
	let chunkSize = $state(500);
	let chunkOverlap = $state(50);
	let autoKgExtract = $state(true);
	let knowledgeLoading = $state(true);
	let knowledgeSaving = $state(false);
	let knowledgeSaved = $state(false);

	// -----------------------------------------------------------------------
	// Embedding status
	// -----------------------------------------------------------------------

	let embeddingStatus = $state<'ok' | 'warning' | 'error' | null>(null);
	let embeddingStatusMessage = $state('');

	// -----------------------------------------------------------------------
	// Global feedback
	// -----------------------------------------------------------------------

	let error = $state('');

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadSearchConfig() {
		searchLoading = true;
		try {
			const config = await apiJson<{
				search_provider: string;
				search_api_key: string;
				search_max_results: number;
			}>('/settings/search');
			searchProvider = config.search_provider || '';
			searchApiKey = config.search_api_key || '';
			searchMaxResults = config.search_max_results || 5;
		} catch {
			// Non-critical — defaults are fine
		} finally {
			searchLoading = false;
		}
	}

	async function loadBranding() {
		brandingLoading = true;
		try {
			const settings = await apiJson<Record<string, string>>('/settings/app');
			appTitle = settings.app_title || 'Firefly Desk';
			accentColor = settings.accent_color || '#2563EB';
		} catch {
			// Defaults are fine
		} finally {
			brandingLoading = false;
		}
	}

	async function loadKnowledgeConfig() {
		knowledgeLoading = true;
		try {
			const config = await apiJson<{
				chunk_size: number;
				chunk_overlap: number;
				chunking_mode: string;
				auto_kg_extract: boolean;
			}>('/settings/knowledge');
			chunkSize = config.chunk_size;
			chunkOverlap = config.chunk_overlap;
			chunkingMode = config.chunking_mode as 'auto' | 'structural' | 'fixed';
			autoKgExtract = config.auto_kg_extract;
		} catch {
			// Defaults are fine
		} finally {
			knowledgeLoading = false;
		}
	}

	async function loadEmbeddingStatus() {
		try {
			const status = await apiJson<{
				status: string;
				message: string;
				dimensions?: number;
			}>('/settings/embedding/status');
			embeddingStatus = status.status as 'ok' | 'warning' | 'error';
			embeddingStatusMessage = status.message;
		} catch {
			embeddingStatus = null;
		}
	}

	// -----------------------------------------------------------------------
	// Save handlers
	// -----------------------------------------------------------------------

	async function saveSearchConfig() {
		searchSaving = true;
		error = '';
		try {
			await apiJson('/settings/search', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					search_provider: searchProvider,
					search_api_key: searchApiKey,
					search_max_results: searchMaxResults
				})
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save search config';
		} finally {
			searchSaving = false;
		}
	}

	async function testSearchConnection() {
		searchTesting = true;
		searchTestResult = null;
		try {
			searchTestResult = await apiJson<{
				success: boolean;
				error?: string;
				result_count?: number;
			}>('/settings/search/test', { method: 'POST' });
		} catch (e) {
			searchTestResult = {
				success: false,
				error: e instanceof Error ? e.message : 'Test failed'
			};
		} finally {
			searchTesting = false;
		}
	}

	async function saveBranding() {
		brandingSaving = true;
		brandingSaved = false;
		error = '';
		try {
			await apiJson('/settings/app', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					app_title: appTitle,
					accent_color: accentColor
				})
			});
			brandingSaved = true;
			setTimeout(() => (brandingSaved = false), 2000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save branding';
		} finally {
			brandingSaving = false;
		}
	}

	async function saveKnowledgeConfig() {
		knowledgeSaving = true;
		knowledgeSaved = false;
		error = '';
		try {
			await apiJson('/settings/knowledge', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					chunk_size: chunkSize,
					chunk_overlap: chunkOverlap,
					chunking_mode: chunkingMode,
					auto_kg_extract: autoKgExtract
				})
			});
			knowledgeSaved = true;
			setTimeout(() => (knowledgeSaved = false), 2000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save knowledge config';
		} finally {
			knowledgeSaving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Init
	// -----------------------------------------------------------------------

	$effect(() => {
		loadSearchConfig();
		loadBranding();
		loadKnowledgeConfig();
		loadEmbeddingStatus();
	});
</script>

<div class="mx-auto max-w-4xl space-y-8 p-6 pb-16">
	<!-- Header -->
	<div>
		<h1 class="text-xl font-semibold text-text-primary">Settings</h1>
		<p class="mt-1 text-sm text-text-secondary">
			Platform-wide configuration for search, branding, and knowledge quality.
		</p>
	</div>

	<!-- Error banner -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
		>
			<XCircle size={16} />
			{error}
			<button
				onclick={() => (error = '')}
				class="ml-auto text-danger/60 hover:text-danger"
			>
				Dismiss
			</button>
		</div>
	{/if}

	<!-- ================================================================= -->
	<!-- Search Engine                                                       -->
	<!-- ================================================================= -->
	<section class="rounded-xl border border-border bg-surface">
		<div class="flex items-center gap-3 border-b border-border/50 px-5 py-4">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
				<Globe size={16} class="text-accent" />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Search Engine</h2>
				<p class="text-xs text-text-secondary">
					Give the agent internet search capabilities for current information.
				</p>
			</div>
		</div>

		<div class="space-y-4 p-5">
			{#if searchLoading}
				<div class="flex items-center justify-center py-6">
					<Loader2 size={20} class="animate-spin text-text-secondary" />
				</div>
			{:else}
				<!-- Provider -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">Provider</label>
					<select
						bind:value={searchProvider}
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
					>
						<option value="">None (disabled)</option>
						<option value="tavily">Tavily</option>
					</select>
					{#if !searchProvider}
						<p class="mt-1.5 text-xs text-text-secondary/70">
							Enable a search provider so the agent can look up real-time information from the web.
						</p>
					{/if}
				</div>

				{#if searchProvider}
					<!-- Tavily setup guide -->
					<div class="rounded-lg border border-accent/20 bg-accent/5 px-4 py-3">
						<p class="text-xs font-medium text-accent">How to get a Tavily API key</p>
						<ol class="mt-1.5 list-inside list-decimal space-y-0.5 text-xs text-text-secondary">
							<li>Visit <span class="font-mono text-accent">tavily.com</span> and create a free account</li>
							<li>Navigate to the API Keys section in your dashboard</li>
							<li>Copy your API key and paste it below</li>
						</ol>
						<p class="mt-1.5 text-xs text-text-secondary/70">
							The free tier includes 1,000 searches/month.
						</p>
					</div>

					<!-- API Key -->
					<div>
						<label class="mb-1.5 block text-xs font-medium text-text-secondary">API Key</label>
						<input
							type="password"
							bind:value={searchApiKey}
							placeholder="tvly-..."
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						/>
					</div>

					<!-- Max Results -->
					<div>
						<label class="mb-1.5 block text-xs font-medium text-text-secondary">
							Max Results per Query: <span class="font-semibold text-text-primary">{searchMaxResults}</span>
						</label>
						<input
							type="range"
							min="1"
							max="10"
							bind:value={searchMaxResults}
							class="w-full accent-accent"
						/>
						<div class="mt-0.5 flex justify-between text-[10px] text-text-secondary/60">
							<span>1</span>
							<span>5</span>
							<span>10</span>
						</div>
					</div>
				{/if}

				<!-- Actions -->
				<div class="flex items-center gap-2 pt-1">
					<button
						type="button"
						onclick={saveSearchConfig}
						disabled={searchSaving}
						class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
					>
						<Save size={14} />
						{searchSaving ? 'Saving...' : 'Save'}
					</button>

					{#if searchProvider}
						<button
							type="button"
							onclick={testSearchConnection}
							disabled={searchTesting}
							class="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
						>
							<TestTube size={14} />
							{searchTesting ? 'Testing...' : 'Test Connection'}
						</button>
					{/if}
				</div>

				<!-- Test result -->
				{#if searchTestResult}
					<div
						class="flex items-center gap-2 rounded-lg border px-4 py-2.5 text-xs {searchTestResult.success
							? 'border-success/30 bg-success/5 text-success'
							: 'border-danger/30 bg-danger/5 text-danger'}"
					>
						{#if searchTestResult.success}
							<CheckCircle size={14} />
							Search working — {searchTestResult.result_count} results returned
						{:else}
							<XCircle size={14} />
							Search test failed: {searchTestResult.error}
						{/if}
					</div>
				{/if}
			{/if}
		</div>
	</section>

	<!-- ================================================================= -->
	<!-- Branding                                                            -->
	<!-- ================================================================= -->
	<section class="rounded-xl border border-border bg-surface">
		<div class="flex items-center gap-3 border-b border-border/50 px-5 py-4">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
				<Palette size={16} class="text-accent" />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Branding</h2>
				<p class="text-xs text-text-secondary">
					Customise the application title and accent colour.
				</p>
			</div>
		</div>

		<div class="space-y-4 p-5">
			{#if brandingLoading}
				<div class="flex items-center justify-center py-6">
					<Loader2 size={20} class="animate-spin text-text-secondary" />
				</div>
			{:else}
				<!-- App title -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">Application Title</label>
					<input
						type="text"
						bind:value={appTitle}
						placeholder="Firefly Desk"
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
					/>
				</div>

				<!-- Accent colour -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">Accent Colour</label>
					<div class="flex items-center gap-3">
						<input
							type="color"
							bind:value={accentColor}
							class="h-9 w-12 cursor-pointer rounded border border-border"
						/>
						<input
							type="text"
							bind:value={accentColor}
							placeholder="#2563EB"
							class="w-32 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-mono text-text-primary outline-none transition-colors focus:border-accent"
						/>
						<div
							class="h-9 flex-1 rounded-lg border border-border"
							style="background-color: {accentColor}"
						></div>
					</div>
				</div>

				<!-- Save -->
				<div class="flex items-center gap-2 pt-1">
					<button
						type="button"
						onclick={saveBranding}
						disabled={brandingSaving}
						class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
					>
						<Save size={14} />
						{brandingSaving ? 'Saving...' : 'Save'}
					</button>
					{#if brandingSaved}
						<span class="flex items-center gap-1 text-xs text-success">
							<CheckCircle size={14} />
							Saved
						</span>
					{/if}
				</div>
			{/if}
		</div>
	</section>

	<!-- ================================================================= -->
	<!-- Knowledge Quality                                                   -->
	<!-- ================================================================= -->
	<section class="rounded-xl border border-border bg-surface">
		<div class="flex items-center gap-3 border-b border-border/50 px-5 py-4">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
				<BookOpen size={16} class="text-accent" />
			</div>
			<div class="flex-1">
				<h2 class="text-sm font-semibold text-text-primary">Knowledge Quality</h2>
				<p class="text-xs text-text-secondary">
					Control how documents are chunked, embedded, and indexed.
				</p>
			</div>
			<!-- Embedding status badge -->
			{#if embeddingStatus}
				<div
					class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium
						{embeddingStatus === 'ok'
						? 'bg-success/10 text-success'
						: embeddingStatus === 'warning'
							? 'bg-warning/10 text-warning'
							: 'bg-danger/10 text-danger'}"
				>
					{#if embeddingStatus === 'ok'}
						<CheckCircle size={12} />
					{:else if embeddingStatus === 'warning'}
						<AlertTriangle size={12} />
					{:else}
						<XCircle size={12} />
					{/if}
					{embeddingStatusMessage}
				</div>
			{/if}
		</div>

		<div class="space-y-4 p-5">
			{#if knowledgeLoading}
				<div class="flex items-center justify-center py-6">
					<Loader2 size={20} class="animate-spin text-text-secondary" />
				</div>
			{:else}
				<!-- Chunking mode -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">Chunking Mode</label>
					<select
						bind:value={chunkingMode}
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
					>
						<option value="auto">Auto (recommended)</option>
						<option value="structural">Structural</option>
						<option value="fixed">Fixed Size</option>
					</select>
					<p class="mt-1.5 text-xs text-text-secondary/70">
						{#if chunkingMode === 'auto'}
							Automatically selects the best chunking strategy based on document structure.
						{:else if chunkingMode === 'structural'}
							Splits on headings and sections, preserving document structure.
						{:else}
							Splits into fixed-size chunks. Best for unstructured text.
						{/if}
					</p>
				</div>

				<!-- Chunk size -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">
						Chunk Size: <span class="font-semibold text-text-primary">{chunkSize}</span> tokens
					</label>
					<input
						type="range"
						min="100"
						max="2000"
						step="50"
						bind:value={chunkSize}
						class="w-full accent-accent"
					/>
					<div class="mt-0.5 flex justify-between text-[10px] text-text-secondary/60">
						<span>100</span>
						<span>500</span>
						<span>1000</span>
						<span>2000</span>
					</div>
				</div>

				<!-- Chunk overlap -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">
						Chunk Overlap: <span class="font-semibold text-text-primary">{chunkOverlap}</span> tokens
					</label>
					<input
						type="range"
						min="0"
						max="200"
						step="10"
						bind:value={chunkOverlap}
						class="w-full accent-accent"
					/>
					<div class="mt-0.5 flex justify-between text-[10px] text-text-secondary/60">
						<span>0</span>
						<span>50</span>
						<span>100</span>
						<span>200</span>
					</div>
				</div>

				<!-- Auto KG extraction -->
				<label class="flex items-center gap-3">
					<input
						type="checkbox"
						bind:checked={autoKgExtract}
						class="h-4 w-4 rounded accent-accent"
					/>
					<div>
						<span class="text-sm text-text-primary">Auto-extract knowledge graph entities</span>
						<p class="text-xs text-text-secondary/70">
							Automatically discover entities and relationships when documents are indexed.
						</p>
					</div>
				</label>

				<!-- Save -->
				<div class="flex items-center gap-2 pt-1">
					<button
						type="button"
						onclick={saveKnowledgeConfig}
						disabled={knowledgeSaving}
						class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
					>
						<Save size={14} />
						{knowledgeSaving ? 'Saving...' : 'Save'}
					</button>
					{#if knowledgeSaved}
						<span class="flex items-center gap-1 text-xs text-success">
							<CheckCircle size={14} />
							Saved
						</span>
					{/if}
				</div>
			{/if}
		</div>
	</section>
</div>
