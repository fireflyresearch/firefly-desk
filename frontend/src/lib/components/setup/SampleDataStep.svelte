<!--
  SampleDataStep.svelte -- Optionally seed the banking demo catalog.

  Offers a single toggle for the "Banking Demo Catalog" dataset. When
  enabled and the user proceeds, POSTs to /api/setup/seed with
  {"domain": "banking"} and shows a loading / success indicator.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight, CheckCircle, Loader2 } from 'lucide-svelte';
	import { apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface SampleDataStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: SampleDataStepProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let includeSampleData = $state(true);
	let seeding = $state(false);
	let seeded = $state(false);
	let error = $state('');

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleContinue() {
		if (!includeSampleData || seeded) {
			onNext({ sample_data: includeSampleData });
			return;
		}

		seeding = true;
		error = '';
		try {
			await apiFetch('/setup/seed', {
				method: 'POST',
				body: JSON.stringify({ domain: 'banking' })
			});
			seeded = true;
			onNext({ sample_data: true });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to seed sample data.';
		} finally {
			seeding = false;
		}
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Sample Data</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Optionally load a demo catalog to explore Firefly Desk right away.
	</p>

	<div class="mt-6">
		<label
			class="flex cursor-pointer items-start gap-4 rounded-lg border px-5 py-4 transition-all
				{includeSampleData
				? 'border-ember bg-ember/5'
				: 'border-border hover:border-text-secondary/40'}"
		>
			<input
				type="checkbox"
				bind:checked={includeSampleData}
				disabled={seeded}
				class="mt-0.5 accent-amber-500"
			/>
			<div class="flex-1">
				<div class="flex items-center gap-2">
					<span class="text-sm font-semibold text-text-primary">Banking Demo Catalog</span>
					{#if seeded}
						<CheckCircle size={16} class="text-success" />
					{/if}
				</div>
				<p class="mt-1 text-xs text-text-secondary">
					Includes sample intents, entities, and conversation flows for a banking
					customer-service scenario. Great for trying out the agent workspace.
				</p>
			</div>
		</label>
	</div>

	<!-- Error -->
	{#if error}
		<div
			class="mt-4 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
		>
			{error}
		</div>
	{/if}

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
			disabled={seeding}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
		>
			{#if seeding}
				<Loader2 size={16} class="animate-spin" />
				Seeding...
			{:else}
				Continue
				<ArrowRight size={16} />
			{/if}
		</button>
	</div>
</div>
