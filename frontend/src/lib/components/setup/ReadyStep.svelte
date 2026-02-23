<!--
  ReadyStep.svelte -- Final confirmation step of the setup wizard.

  Displays a summary of everything that was configured (LLM provider,
  dev user, sample data) and a "Launch Firefly Desk" button that calls
  POST /api/setup/complete then redirects to "/".

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Flame, ArrowLeft, Loader2 } from 'lucide-svelte';
	import { apiFetch } from '$lib/services/api.js';

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
	let error = $state('');

	// -----------------------------------------------------------------------
	// Derived summary
	// -----------------------------------------------------------------------

	interface SummaryRow {
		label: string;
		value: string;
	}

	let summaryRows: SummaryRow[] = $derived.by(() => {
		const rows: SummaryRow[] = [];

		// LLM provider
		const llm = wizardData.llm_provider as Record<string, unknown> | null | undefined;
		rows.push({
			label: 'LLM Provider',
			value: llm ? (llm.name as string) ?? 'Configured' : 'Skipped'
		});

		// Dev user
		const devUser = wizardData.dev_user as Record<string, unknown> | undefined;
		if (devUser) {
			rows.push({
				label: 'Dev User',
				value: `${devUser.display_name ?? 'Dev Admin'} (${devUser.role ?? 'admin'})`
			});
		}

		// Sample data
		rows.push({
			label: 'Sample Data',
			value: wizardData.sample_data ? 'Banking Demo' : 'None'
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
			await apiFetch('/setup/complete', { method: 'POST' });
			window.location.href = '/';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to complete setup.';
			launching = false;
		}
	}
</script>

<div class="flex h-full flex-col items-center justify-center text-center">
	<!-- Success icon -->
	<div
		class="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-success/10 text-success"
	>
		<Flame size={32} />
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
				<span class="font-medium text-text-primary">{row.value}</span>
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
		disabled={launching}
		class="btn-hover mt-8 inline-flex items-center gap-2 rounded-lg bg-ember px-8 py-2.5 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
	>
		{#if launching}
			<Loader2 size={16} class="animate-spin" />
			Launching...
		{:else}
			Launch Firefly Desk
		{/if}
	</button>

	<!-- Back link (below launch) -->
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
