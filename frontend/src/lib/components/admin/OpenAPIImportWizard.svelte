<!--
  OpenAPIImportWizard.svelte - 3-step wizard for importing external systems
  from an OpenAPI specification.

  Step 1: Source - Paste OpenAPI JSON spec (or URL, coming soon).
  Step 2: Preview - Review parsed system info and select endpoints.
  Step 3: Confirm - Set system name, auth type, and import.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		ChevronLeft,
		ChevronRight,
		Upload,
		Loader2,
		Check,
		CheckSquare,
		Square
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface ParsedParameter {
		name: string;
		in: string;
		required: boolean;
		description: string;
		type: string;
	}

	interface ParsedEndpoint {
		path: string;
		method: string;
		operation_id: string;
		summary: string;
		description: string;
		parameters: ParsedParameter[];
		request_body_schema: unknown;
		tags: string[];
	}

	interface AuthScheme {
		name: string;
		type: string;
		scheme?: string;
	}

	interface ParsedSpec {
		title: string;
		description: string;
		version: string;
		base_url: string;
		auth_schemes: AuthScheme[];
		endpoints: ParsedEndpoint[];
	}

	interface ConfirmResponse {
		system_id: string;
		endpoint_count: number;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let {
		onClose,
		onImported
	}: {
		onClose: () => void;
		onImported: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Source', 'Preview', 'Confirm'] as const;

	const AUTH_TYPES = [
		{ value: 'none', label: 'None' },
		{ value: 'bearer', label: 'Bearer Token' },
		{ value: 'api_key', label: 'API Key' },
		{ value: 'basic', label: 'Basic Auth' },
		{ value: 'oauth2', label: 'OAuth 2.0' },
		{ value: 'mutual_tls', label: 'Mutual TLS' }
	] as const;

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let error = $state('');

	// Step 1: Source
	let specText = $state('');
	let urlText = $state('');
	let parsing = $state(false);

	// Step 2: Preview (populated after parse)
	let parsedSpec = $state<ParsedSpec | null>(null);
	let selectedIndices = $state<Set<number>>(new Set());

	// Step 3: Confirm
	let systemName = $state('');
	let authType = $state('none');
	let importing = $state(false);
	let importResult = $state<ConfirmResponse | null>(null);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let allSelected = $derived(
		parsedSpec !== null &&
			parsedSpec.endpoints.length > 0 &&
			selectedIndices.size === parsedSpec.endpoints.length
	);

	let selectedCount = $derived(selectedIndices.size);

	let totalEndpoints = $derived(parsedSpec?.endpoints.length ?? 0);

	// -----------------------------------------------------------------------
	// Step 1: Parse
	// -----------------------------------------------------------------------

	async function parseSpec() {
		error = '';
		parsing = true;

		try {
			const specJson = JSON.parse(specText.trim());
			parsedSpec = await apiJson<ParsedSpec>('/catalog/import/openapi/parse', {
				method: 'POST',
				body: JSON.stringify({ spec: specJson })
			});

			// Select all endpoints by default
			selectedIndices = new Set(parsedSpec.endpoints.map((_, i) => i));

			// Pre-fill system name from parsed title
			systemName = parsedSpec.title;

			// Auto-detect auth type from parsed auth schemes
			if (parsedSpec.auth_schemes.length > 0) {
				const first = parsedSpec.auth_schemes[0];
				if (first.type === 'http' && first.scheme === 'bearer') {
					authType = 'bearer';
				} else if (first.type === 'http' && first.scheme === 'basic') {
					authType = 'basic';
				} else if (first.type === 'apiKey') {
					authType = 'api_key';
				} else if (first.type === 'oauth2') {
					authType = 'oauth2';
				} else if (first.type === 'mutualTLS') {
					authType = 'mutual_tls';
				}
			}

			currentStep = 1;
		} catch (e) {
			if (e instanceof SyntaxError) {
				error = 'Invalid JSON. Please paste a valid OpenAPI specification in JSON format.';
			} else {
				error = e instanceof Error ? e.message : 'Failed to parse OpenAPI specification';
			}
		} finally {
			parsing = false;
		}
	}

	// -----------------------------------------------------------------------
	// Step 2: Selection
	// -----------------------------------------------------------------------

	function toggleEndpoint(index: number) {
		const next = new Set(selectedIndices);
		if (next.has(index)) {
			next.delete(index);
		} else {
			next.add(index);
		}
		selectedIndices = next;
	}

	function toggleAll() {
		if (allSelected) {
			selectedIndices = new Set();
		} else {
			selectedIndices = new Set(parsedSpec!.endpoints.map((_, i) => i));
		}
	}

	// -----------------------------------------------------------------------
	// Step 3: Import
	// -----------------------------------------------------------------------

	async function confirmImport() {
		if (!parsedSpec || selectedIndices.size === 0) return;

		error = '';
		importing = true;

		const selectedEndpoints = parsedSpec.endpoints
			.filter((_, i) => selectedIndices.has(i))
			.map((ep) => ({
				path: ep.path,
				method: ep.method,
				operation_id: ep.operation_id,
				summary: ep.summary,
				description: ep.description,
				parameters: ep.parameters,
				tags: ep.tags
			}));

		try {
			importResult = await apiJson<ConfirmResponse>('/catalog/import/openapi/confirm', {
				method: 'POST',
				body: JSON.stringify({
					parsed_spec: {
						title: parsedSpec.title,
						description: parsedSpec.description,
						base_url: parsedSpec.base_url
					},
					selected_endpoints: selectedEndpoints,
					system_name: systemName.trim(),
					auth_type: authType
				})
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to import system';
		} finally {
			importing = false;
		}
	}

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	function goNext() {
		if (currentStep < STEPS.length - 1) {
			currentStep += 1;
		}
	}

	function goPrev() {
		if (currentStep > 0) {
			error = '';
			currentStep -= 1;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

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

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}

	function isStepComplete(step: number): boolean {
		if (step === 0) return parsedSpec !== null;
		if (step === 1) return parsedSpec !== null && selectedIndices.size > 0;
		if (step === 2) return importResult !== null;
		return false;
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Modal backdrop -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
	role="presentation"
	onclick={handleBackdropClick}
>
	<!-- Modal content -->
	<div class="mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-surface shadow-2xl">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-border px-6 py-4">
			<h2 class="text-base font-semibold text-text-primary">Import from OpenAPI</h2>
			<button
				type="button"
				onclick={onClose}
				class="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			>
				<X size={18} />
			</button>
		</div>

		<!-- Step indicators -->
		<div class="flex items-center gap-2 border-b border-border px-6 py-3">
			{#each STEPS as stepLabel, i}
				{@const active = i === currentStep}
				{@const complete = isStepComplete(i)}

				{#if i > 0}
					<div class="h-px flex-1 {i <= currentStep ? 'bg-accent' : 'bg-border'}"></div>
				{/if}

				<div
					class="flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium
						{active ? 'text-accent' : complete ? 'text-success' : 'text-text-secondary'}"
				>
					<span
						class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold
							{active ? 'bg-accent text-white' : complete ? 'bg-success text-white' : 'bg-surface-secondary text-text-secondary'}"
					>
						{#if complete}
							<Check size={12} />
						{:else}
							{i + 1}
						{/if}
					</span>
					<span class="hidden sm:inline">{stepLabel}</span>
				</div>
			{/each}
		</div>

		<!-- Error banner -->
		{#if error}
			<div
				class="mx-6 mt-4 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
			>
				{error}
			</div>
		{/if}

		<!-- Step content -->
		<div class="flex-1 overflow-y-auto px-6 py-5">
			<!-- Step 1: Source -->
			{#if currentStep === 0}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Paste an OpenAPI 3.x specification in JSON format to import a system and its
						endpoints.
					</p>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary"
							>OpenAPI Specification (JSON) <span class="text-danger">*</span></span
						>
						<textarea
							bind:value={specText}
							rows={12}
							placeholder={'{"openapi": "3.0.0", "info": {"title": "My API", ...}, "paths": {...}}'}
							class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
						></textarea>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary"
							>Or import from URL
							<span
								class="ml-1 rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] font-medium text-text-secondary"
								>Coming soon</span
							></span
						>
						<input
							type="url"
							bind:value={urlText}
							disabled
							placeholder="https://example.com/openapi.json"
							class="rounded-md border border-border bg-surface-secondary px-3 py-2 font-mono text-sm text-text-secondary outline-none disabled:cursor-not-allowed disabled:opacity-60"
						/>
					</label>
				</div>

				<!-- Step 2: Preview -->
			{:else if currentStep === 1 && parsedSpec}
				<div class="flex flex-col gap-4">
					<!-- System info card -->
					<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
						<h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
							Parsed System
						</h3>
						<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
							<span class="text-text-secondary">Title:</span>
							<span class="font-medium text-text-primary">{parsedSpec.title}</span>
							{#if parsedSpec.description}
								<span class="text-text-secondary">Description:</span>
								<span class="text-text-primary">{parsedSpec.description}</span>
							{/if}
							<span class="text-text-secondary">Version:</span>
							<span class="font-mono text-xs text-text-primary">{parsedSpec.version}</span>
							{#if parsedSpec.base_url}
								<span class="text-text-secondary">Base URL:</span>
								<span class="font-mono text-xs text-text-primary">{parsedSpec.base_url}</span>
							{/if}
							{#if parsedSpec.auth_schemes.length > 0}
								<span class="text-text-secondary">Auth Schemes:</span>
								<span class="text-text-primary">
									{parsedSpec.auth_schemes.map((s) => s.name).join(', ')}
								</span>
							{/if}
						</div>
					</div>

					<!-- Endpoint selection header -->
					<div class="flex items-center justify-between">
						<span class="text-sm font-medium text-text-primary">
							{selectedCount} of {totalEndpoints} endpoints selected
						</span>
						<button
							type="button"
							onclick={toggleAll}
							class="text-xs font-medium text-accent transition-colors hover:text-accent-hover"
						>
							{allSelected ? 'Deselect All' : 'Select All'}
						</button>
					</div>

					<!-- Endpoint table -->
					<div class="rounded-lg border border-border bg-surface">
						<div class="overflow-x-auto">
							<table class="w-full text-left text-sm">
								<thead>
									<tr class="border-b border-border bg-surface-secondary">
										<th class="w-10 px-3 py-2">
											<button
												type="button"
												onclick={toggleAll}
												class="text-text-secondary hover:text-text-primary"
											>
												{#if allSelected}
													<CheckSquare size={16} />
												{:else}
													<Square size={16} />
												{/if}
											</button>
										</th>
										<th class="w-20 px-3 py-2 text-xs font-medium text-text-secondary"
											>Method</th
										>
										<th class="px-3 py-2 text-xs font-medium text-text-secondary">Path</th>
										<th class="px-3 py-2 text-xs font-medium text-text-secondary"
										>Summary / Description</th
										>
										<th class="px-3 py-2 text-xs font-medium text-text-secondary">Tags</th>
									</tr>
								</thead>
								<tbody>
									{#each parsedSpec.endpoints as ep, i}
										{@const selected = selectedIndices.has(i)}
										<tr
											class="border-b border-border last:border-b-0 cursor-pointer transition-colors
												{selected ? 'bg-accent/5' : 'hover:bg-surface-hover'}"
											onclick={() => toggleEndpoint(i)}
										>
											<td class="px-3 py-2">
												<span class="text-text-secondary">
													{#if selected}
														<CheckSquare size={16} class="text-accent" />
													{:else}
														<Square size={16} />
													{/if}
												</span>
											</td>
											<td class="px-3 py-2">
												<span
													class="rounded px-1.5 py-0.5 font-mono text-xs font-medium {methodVariant(ep.method)}"
												>
													{ep.method.toUpperCase()}
												</span>
											</td>
											<td class="px-3 py-2 font-mono text-xs text-text-primary">
												{ep.path}
											</td>
											<td class="px-3 py-2">
												<input
													type="text"
													value={ep.summary}
													oninput={(e) => { if (parsedSpec) parsedSpec.endpoints[i].summary = e.currentTarget.value; }}
													class="w-full bg-transparent text-sm text-text-primary outline-none focus:border-b focus:border-accent"
													placeholder="Summary"
													onclick={(e) => e.stopPropagation()}
												/>
												<input
													type="text"
													value={ep.description ?? ''}
													oninput={(e) => { if (parsedSpec) parsedSpec.endpoints[i].description = e.currentTarget.value; }}
													class="mt-0.5 w-full bg-transparent text-xs text-text-secondary outline-none focus:border-b focus:border-accent"
													placeholder="Description (optional)"
													onclick={(e) => e.stopPropagation()}
												/>
											</td>
											<td class="px-3 py-2">
												{#if ep.tags && ep.tags.length > 0}
													<div class="flex flex-wrap gap-1">
														{#each ep.tags as tag}
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
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				</div>

				<!-- Step 3: Confirm -->
			{:else if currentStep === 2}
				{#if importResult}
					<!-- Success state -->
					<div class="flex flex-col items-center gap-4 py-8">
						<div
							class="flex h-12 w-12 items-center justify-center rounded-full bg-success/10"
						>
							<Check size={24} class="text-success" />
						</div>
						<h3 class="text-lg font-semibold text-text-primary">Import Successful</h3>
						<p class="text-sm text-text-secondary">
							System created with {importResult.endpoint_count} endpoint{importResult.endpoint_count !== 1 ? 's' : ''}.
						</p>
						<div class="rounded-md border border-border bg-surface-secondary/50 px-4 py-2">
							<span class="text-xs text-text-secondary">System ID: </span>
							<code class="font-mono text-sm text-text-primary">{importResult.system_id}</code>
						</div>
					</div>
				{:else}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Configure the imported system before creating it.
						</p>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary"
								>System Name <span class="text-danger">*</span></span
							>
							<input
								type="text"
								bind:value={systemName}
								required
								placeholder="e.g. Pet Store API"
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Authentication Type</span
							>
							<select
								bind:value={authType}
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							>
								{#each AUTH_TYPES as type}
									<option value={type.value}>{type.label}</option>
								{/each}
							</select>
						</label>

						<!-- Review summary -->
						<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
							<h4
								class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary"
							>
								Import Summary
							</h4>
							<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
								<span class="text-text-secondary">System:</span>
								<span class="font-medium text-text-primary">{systemName || '--'}</span>
								{#if parsedSpec?.base_url}
									<span class="text-text-secondary">Base URL:</span>
									<span class="font-mono text-xs text-text-primary"
										>{parsedSpec.base_url}</span
									>
								{/if}
								<span class="text-text-secondary">Auth Type:</span>
								<span class="text-text-primary"
									>{AUTH_TYPES.find((t) => t.value === authType)?.label ?? authType}</span
								>
								<span class="text-text-secondary">Endpoints:</span>
								<span class="text-text-primary">{selectedCount} selected</span>
							</div>
						</div>
					</div>
				{/if}
			{/if}
		</div>

		<!-- Footer navigation -->
		<div class="flex items-center justify-between border-t border-border px-6 py-4">
			<div>
				{#if currentStep > 0 && !importResult}
					<button
						type="button"
						onclick={goPrev}
						class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						<ChevronLeft size={14} />
						Back
					</button>
				{/if}
			</div>

			<div class="flex items-center gap-2">
				{#if importResult}
					<button
						type="button"
						onclick={() => { onImported(); }}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
					>
						<Check size={14} />
						Done
					</button>
				{:else}
					<button
						type="button"
						onclick={onClose}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>

					{#if currentStep === 0}
						<button
							type="button"
							onclick={parseSpec}
							disabled={parsing || !specText.trim()}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if parsing}
								<Loader2 size={14} class="animate-spin" />
								Parsing...
							{:else}
								Parse
								<ChevronRight size={14} />
							{/if}
						</button>
					{:else if currentStep === 1}
						<button
							type="button"
							onclick={goNext}
							disabled={selectedCount === 0}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							Next
							<ChevronRight size={14} />
						</button>
					{:else if currentStep === 2}
						<button
							type="button"
							onclick={confirmImport}
							disabled={importing || !systemName.trim() || selectedCount === 0}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if importing}
								<Loader2 size={14} class="animate-spin" />
								Importing...
							{:else}
								<Upload size={14} />
								Import
							{/if}
						</button>
					{/if}
				{/if}
			</div>
		</div>
	</div>
</div>
