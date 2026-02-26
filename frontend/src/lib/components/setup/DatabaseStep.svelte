<!--
  DatabaseStep.svelte -- Database configuration step of the setup wizard.

  Shows the current database type (SQLite for dev, PostgreSQL for production).
  In dev mode, allows switching between SQLite and PostgreSQL.
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
		Database,
		Info
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

	let devMode = $derived(status?.dev_mode === true);
	let currentDbType = $derived((status?.database_type as string) ?? 'sqlite');

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let selectedDbType = $state<'sqlite' | 'postgresql'>('sqlite');
	let connectionString = $state('');
	let testing = $state(false);
	let testResult = $state<'success' | 'failure' | null>(null);
	let testMessage = $state('');
	let testedCurrentDb = $state(false);
	let autoTested = $state(false);

	// Sync selected type from status on first load
	$effect(() => {
		if (currentDbType === 'postgresql') {
			selectedDbType = 'postgresql';
		}
	});

	let showPostgresForm = $derived(selectedDbType === 'postgresql');

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleTypeChange(type: 'sqlite' | 'postgresql') {
		selectedDbType = type;
		testResult = null;
		testMessage = '';
		testedCurrentDb = false;
		if (type === 'sqlite') {
			autoTested = false;
		}
	}

	async function testConnection() {
		testing = true;
		testResult = null;
		testMessage = '';

		try {
			const body: Record<string, string> = {};
			if (showPostgresForm && connectionString.trim()) {
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
				type: selectedDbType,
				tested: testedCurrentDb || testResult === 'success'
			}
		});
	}

	// Auto-test the current database on mount for SQLite (one-shot)
	$effect(() => {
		if (selectedDbType === 'sqlite' && !autoTested) {
			autoTested = true;
			testConnection();
		}
	});
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Database</h2>
	<p class="mt-1 text-sm text-text-secondary">
		{#if devMode}
			Choose your database and verify the connection.
		{:else}
			Verify your database connection before continuing.
		{/if}
	</p>

	<div class="mt-6 space-y-5">
		<!-- Database type selector (dev mode only) -->
		{#if devMode}
			<div class="grid grid-cols-2 gap-3">
				<button
					type="button"
					onclick={() => handleTypeChange('sqlite')}
					class="flex flex-col items-center gap-2 rounded-lg border px-4 py-4 text-sm font-medium transition-colors
						{selectedDbType === 'sqlite'
						? 'border-ember bg-ember/5 text-ember'
						: 'border-border bg-surface-secondary text-text-secondary hover:border-border-hover'}"
				>
					<Database size={20} />
					<span>SQLite</span>
					<span class="text-[11px] font-normal opacity-70">Development</span>
				</button>
				<button
					type="button"
					onclick={() => handleTypeChange('postgresql')}
					class="flex flex-col items-center gap-2 rounded-lg border px-4 py-4 text-sm font-medium transition-colors
						{selectedDbType === 'postgresql'
						? 'border-ember bg-ember/5 text-ember'
						: 'border-border bg-surface-secondary text-text-secondary hover:border-border-hover'}"
				>
					<Database size={20} />
					<span>PostgreSQL</span>
					<span class="text-[11px] font-normal opacity-70">Production-ready</span>
				</button>
			</div>
		{:else}
			<!-- Production: show current database info card -->
			<div
				class="flex items-start gap-4 rounded-lg border border-border bg-surface-secondary px-5 py-4"
			>
				<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ember/10">
					<Database size={20} class="text-ember" />
				</div>
				<div class="flex-1">
					<span class="block text-sm font-semibold text-text-primary">
						{currentDbType === 'postgresql' ? 'PostgreSQL' : 'SQLite (Development)'}
					</span>
					{#if currentDbType === 'postgresql'}
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
		{/if}

		<!-- PostgreSQL connection string input -->
		{#if showPostgresForm}
			<div>
				<label
					for="connection-string"
					class="mb-1.5 block text-xs font-medium text-text-secondary"
				>
					Connection String
					{#if currentDbType === 'postgresql'}
						<span class="text-text-secondary/60">(optional override)</span>
					{/if}
				</label>
				<input
					id="connection-string"
					type="text"
					bind:value={connectionString}
					placeholder="postgresql+asyncpg://user:pass@host:5432/dbname"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
				<p class="mt-1 text-[11px] text-text-secondary">
					{#if currentDbType === 'postgresql'}
						Leave empty to test the currently configured database connection.
					{:else}
						Enter your PostgreSQL connection string to test connectivity.
					{/if}
				</p>
			</div>
		{/if}

		<!-- Test Connection button (always show for PostgreSQL, auto-test for SQLite) -->
		{#if showPostgresForm}
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
		{:else if selectedDbType === 'sqlite' && testing}
			<div class="flex items-center gap-2 text-sm text-text-secondary">
				<Loader2 size={16} class="animate-spin" />
				<span>Verifying database...</span>
			</div>
		{/if}

		<!-- Restart notice when switching DB type in dev mode -->
		{#if devMode && selectedDbType !== currentDbType}
			<div
				class="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600 dark:text-amber-400"
			>
				<Info size={18} class="mt-0.5 shrink-0" />
				<span>Changing the database requires restarting the server.</span>
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
