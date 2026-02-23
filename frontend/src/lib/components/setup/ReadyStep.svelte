<!--
  ReadyStep.svelte -- Final confirmation step of the setup wizard.

  Displays a summary of everything configured (database, LLM provider,
  embeddings, agent settings, sample data) and a "Launch Firefly Desk"
  button that calls POST /api/setup/configure to persist everything
  then redirects to "/".

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { ArrowLeft, Loader2, CheckCircle } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import EmberAvatar from '$lib/components/chat/EmberAvatar.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface ConfigureResult {
		success: boolean;
		message: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface ReadyStepProps {
		wizardData: Record<string, unknown>;
		onBack: () => void;
	}

	let { wizardData, onBack }: ReadyStepProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let launching = $state(false);
	let mountChecking = $state(true);
	let error = $state('');

	// -----------------------------------------------------------------------
	// Guard: redirect if setup is already completed (e.g. back-button)
	// -----------------------------------------------------------------------

	onMount(async () => {
		try {
			const status = await apiJson<{ setup_completed?: boolean }>('/setup/status');
			if (status?.setup_completed) {
				window.location.href = '/';
				return;
			}
		} catch {
			// Status endpoint failed — allow the wizard to proceed normally
		}
		mountChecking = false;
	});

	// -----------------------------------------------------------------------
	// Derived summary
	// -----------------------------------------------------------------------

	interface SummaryRow {
		label: string;
		value: string;
		ok: boolean;
	}

	let summaryRows: SummaryRow[] = $derived.by(() => {
		const rows: SummaryRow[] = [];

		// Database
		const db = wizardData.database as Record<string, unknown> | undefined;
		if (db) {
			const dbType = (db.type as string) === 'postgresql' ? 'PostgreSQL' : 'SQLite';
			rows.push({
				label: 'Database',
				value: dbType,
				ok: true
			});
		}

		// LLM Provider
		const llm = wizardData.llm_provider as Record<string, unknown> | null | undefined;
		if (llm) {
			rows.push({
				label: 'LLM Provider',
				value: (llm.name as string) ?? 'Configured',
				ok: true
			});
			if (llm.model_name || llm.model_id) {
				rows.push({
					label: 'Model',
					value: (llm.model_name as string) ?? (llm.model_id as string) ?? '',
					ok: true
				});
			}
		} else {
			rows.push({ label: 'LLM Provider', value: 'Skipped', ok: false });
		}

		// Embedding
		const embedding = wizardData.embedding as Record<string, unknown> | null | undefined;
		if (embedding) {
			const embModel = (embedding.model as string) ?? 'Configured';
			rows.push({
				label: 'Embeddings',
				value: embModel,
				ok: true
			});
		}

		// Vector store
		const vectorStore = wizardData.vector_store as Record<string, unknown> | undefined;
		if (vectorStore && vectorStore.type) {
			const storeNames: Record<string, string> = {
				sqlite: 'SQLite',
				pgvector: 'pgvector',
				chromadb: 'ChromaDB',
				pinecone: 'Pinecone'
			};
			rows.push({
				label: 'Vector Store',
				value: storeNames[vectorStore.type as string] ?? (vectorStore.type as string),
				ok: true
			});
		}

		// Agent settings
		const agent = wizardData.agent_settings as Record<string, unknown> | undefined;
		if (agent) {
			const agentName = (agent.display_name as string) || (agent.name as string) || 'Ember';
			const agentTone = (agent.tone as string) || 'friendly';
			rows.push({
				label: 'Agent',
				value: `${agentName} (${agentTone})`,
				ok: true
			});
		}

		// Dev user
		const devUser = wizardData.dev_user as Record<string, unknown> | undefined;
		if (devUser) {
			rows.push({
				label: 'Dev User',
				value: `${devUser.display_name ?? 'Dev Admin'} (${devUser.role ?? 'admin'})`,
				ok: true
			});
		}

		// Sample data
		rows.push({
			label: 'Sample Data',
			value: wizardData.sample_data ? 'Banking Demo' : 'None',
			ok: !!wizardData.sample_data
		});

		return rows;
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleLaunch() {
		launching = true;
		error = '';
		try {
			const llm = wizardData.llm_provider as Record<string, unknown> | null | undefined;
			const agent = wizardData.agent_settings as Record<string, unknown> | undefined;

			// Build the configure request body
			const configureBody: Record<string, unknown> = {
				seed_data: wizardData.sample_data === true
			};

			if (llm) {
				configureBody.llm_provider = {
					name: llm.name,
					provider_type: llm.provider_type,
					api_key: llm.api_key ?? null,
					base_url: llm.base_url ?? null,
					model_id: llm.model_id ?? null,
					model_name: llm.model_name ?? null
				};
			}

			if (agent) {
				configureBody.agent_settings = {
					name: agent.name ?? 'Ember',
					display_name: agent.display_name ?? agent.name ?? 'Ember',
					personality: agent.personality ?? 'warm, professional, knowledgeable',
					tone: agent.tone ?? 'friendly',
					greeting:
						agent.greeting ?? "Hello! I'm {name}, your intelligent assistant."
				};
			}

			const embedding = wizardData.embedding as Record<string, unknown> | null;
			if (embedding) {
				configureBody.embedding = {
					provider: embedding.provider,
					model: embedding.model,
					api_key: embedding.api_key ?? null,
					base_url: embedding.base_url ?? null,
					dimensions: embedding.dimensions ?? 1536
				};
			}

			const vectorStore = wizardData.vector_store as Record<string, unknown> | undefined;
			if (vectorStore) {
				configureBody.vector_store = vectorStore;
			}

			const result = await apiJson<ConfigureResult>('/setup/configure', {
				method: 'POST',
				body: JSON.stringify(configureBody)
			});

			if (!result.success) {
				error = result.message || 'Configuration failed. Please try again.';
				return;
			}

			window.location.href = '/';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to complete setup.';
		} finally {
			launching = false;
		}
	}
</script>

<div class="flex h-full flex-col items-center justify-center text-center">
	<!-- Success icon -->
	<div class="mb-6">
		<EmberAvatar size={56} />
	</div>

	<h2 class="text-2xl font-bold text-text-primary">Ready to Launch</h2>
	<p class="mt-2 text-sm text-text-secondary">
		Your instance is configured. Here's a summary of what was set up.
	</p>

	<!-- Summary table -->
	<div
		class="mx-auto mt-8 w-full max-w-sm overflow-hidden rounded-lg border border-border text-sm"
	>
		{#each summaryRows as row, i}
			<div
				class="flex items-center justify-between px-4 py-3
					{i < summaryRows.length - 1 ? 'border-b border-border' : ''}"
			>
				<span class="text-text-secondary">{row.label}</span>
				<span class="flex items-center gap-1.5 font-medium text-text-primary">
					{#if row.ok}
						<CheckCircle size={14} class="text-success" />
					{/if}
					{row.value}
				</span>
			</div>
		{/each}
	</div>

	<!-- Error -->
	{#if error}
		<div
			class="mt-4 w-full max-w-sm rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
		>
			{error}
		</div>
	{/if}

	<!-- Launch button -->
	<button
		type="button"
		onclick={handleLaunch}
		disabled={launching || mountChecking}
		class="btn-hover mt-8 inline-flex items-center gap-2 rounded-lg bg-ember px-8 py-2.5 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
	>
		{#if launching}
			<Loader2 size={16} class="animate-spin" />
			Launching...
		{:else}
			Launch Firefly Desk
		{/if}
	</button>

	<!-- Back link -->
	<div class="mt-6">
		<button
			type="button"
			onclick={onBack}
			class="inline-flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text-primary"
		>
			<ArrowLeft size={14} />
			Back
		</button>
	</div>
</div>
