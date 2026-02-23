<!--
  DatabaseStep.svelte -- Database configuration step of the setup wizard.

  Shows the current database type (SQLite for dev, PostgreSQL for production).
  For PostgreSQL, allows entering and testing a connection string.
  For SQLite, confirms the dev database is ready.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		ArrowLeft,
		ArrowRight,
		CheckCircle,
		XCircle,
		Loader2,
		Database
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface DatabaseStepProps {
		status: Record<string, unknown> | null;
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { status, onNext, onBack }: DatabaseStepProps = $props();

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let isPostgres = $derived(status?.database_configured === true);
	let dbLabel = $derived(isPostgres ? 'PostgreSQL' : 'SQLite (Development)');

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let connectionString = $state('');
	let testing = $state(false);
	let testResult = $state<'success' | 'failure' | null>(null);
	let testMessage = $state('');
	let testedCurrentDb = $state(false);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function testConnection() {
		testing = true;
		testResult = null;
		testMessage = '';

		try {
			const body: Record<string, string> = {};
			if (isPostgres && connectionString.trim()) {
				body.connection_string = connectionString.trim();
			}

			const result = await apiJson<{
				success: boolean;
				database_type: string;
				error?: string;
			}>('/setup/test-database', {
				method: 'POST',
				body: JSON.stringify(body)
			});

			if (result.success) {
				testResult = 'success';
				testMessage = `Connected to ${result.database_type} successfully.`;
				testedCurrentDb = true;
			} else {
				testResult = 'failure';
				testMessage = result.error ?? 'Connection test failed.';
			}
		} catch (e) {
			testResult = 'failure';
			testMessage = e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			testing = false;
		}
	}

	function handleContinue() {
		onNext({
			database: {
				type: isPostgres ? 'postgresql' : 'sqlite',
				tested: testedCurrentDb || testResult === 'success'
			}
		});
	}

	// Auto-test the current database on mount for SQLite
	$effect(() => {
		if (!isPostgres && !testedCurrentDb && !testing) {
			testConnection();
		}
	});
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Database</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Verify your database connection before continuing.
	</p>

	<div class="mt-6 space-y-5">
		<!-- Current database info card -->
		<div
			class="flex items-start gap-4 rounded-lg border border-border bg-surface-secondary px-5 py-4"
		>
			<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ember/10">
				<Database size={20} class="text-ember" />
			</div>
			<div class="flex-1">
				<span class="block text-sm font-semibold text-text-primary">{dbLabel}</span>
				{#if isPostgres}
					<p class="mt-0.5 text-xs text-text-secondary">
						Your instance is configured to use PostgreSQL. You can test the connection
						below or provide a different connection string.
					</p>
				{:else}
					<p class="mt-0.5 text-xs text-text-secondary">
						Using an embedded SQLite database for development. No additional
						configuration is needed.
					</p>
				{/if}
			</div>
		</div>

		<!-- PostgreSQL connection string input -->
		{#if isPostgres}
			<div>
				<label
					for="connection-string"
					class="mb-1.5 block text-xs font-medium text-text-secondary"
				>
					Connection String <span class="text-text-secondary/60">(optional override)</span>
				</label>
				<input
					id="connection-string"
					type="text"
					bind:value={connectionString}
					placeholder="postgresql+asyncpg://user:pass@host:5432/dbname"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
				<p class="mt-1 text-[11px] text-text-secondary">
					Leave empty to test the currently configured database connection.
				</p>
			</div>
		{/if}

		<!-- Test Connection button -->
		{#if isPostgres}
			<button
				type="button"
				onclick={testConnection}
				disabled={testing}
				class="btn-hover inline-flex items-center gap-2 rounded-lg bg-ember px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
			>
				{#if testing}
					<Loader2 size={16} class="animate-spin" />
					Testing...
				{:else}
					Test Connection
				{/if}
			</button>
		{/if}

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
		{:else if !isPostgres && testing}
			<div class="flex items-center gap-2 text-sm text-text-secondary">
				<Loader2 size={16} class="animate-spin" />
				<span>Verifying database...</span>
			</div>
		{/if}
	</div>

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Navigation -->
	<div class="mt-8 flex items-center justify-between border-t border-border pt-4">
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
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm"
		>
			Continue
			<ArrowRight size={16} />
		</button>
	</div>
</div>
