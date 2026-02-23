<!--
  SampleDataStep.svelte -- Optionally seed demo data for the instance.

  Offers checkboxes for different data categories: Systems & APIs,
  Knowledge Base docs, Skills (coming soon), and Knowledge Graph entities
  (coming soon). Shows a progress bar during seeding.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight, CheckCircle, Loader2, Lock } from 'lucide-svelte';
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
	// Seed category definitions
	// -----------------------------------------------------------------------

	interface SeedCategory {
		id: string;
		label: string;
		description: string;
		defaultOn: boolean;
		disabled: boolean;
		comingSoon: boolean;
	}

	const categories: SeedCategory[] = [
		{
			id: 'systems',
			label: 'Systems & APIs',
			description:
				'Banking systems with 5 systems, 16 API endpoints, and integration metadata.',
			defaultOn: true,
			disabled: false,
			comingSoon: false
		},
		{
			id: 'knowledge',
			label: 'Knowledge Base',
			description:
				'5 knowledge documents covering banking policies, procedures, and FAQs.',
			defaultOn: true,
			disabled: false,
			comingSoon: false
		},
		{
			id: 'skills',
			label: 'Skills',
			description: 'Banking domain skills for automated task handling.',
			defaultOn: false,
			disabled: true,
			comingSoon: true
		},
		{
			id: 'knowledge_graph',
			label: 'Knowledge Graph',
			description: 'Entity and relationship data for semantic exploration.',
			defaultOn: false,
			disabled: true,
			comingSoon: true
		}
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let selected = $state<Record<string, boolean>>(
		Object.fromEntries(categories.map((c) => [c.id, c.defaultOn]))
	);
	let seeding = $state(false);
	let seeded = $state(false);
	let error = $state('');
	let progress = $state(0);

	let anythingSelected = $derived(
		Object.entries(selected).some(([id, on]) => {
			const cat = categories.find((c) => c.id === id);
			return on && cat && !cat.disabled;
		})
	);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleContinue() {
		if (!anythingSelected || seeded) {
			onNext({ sample_data: seeded || anythingSelected });
			return;
		}

		seeding = true;
		error = '';
		progress = 0;

		try {
			// Seed banking catalog (systems + knowledge in one call)
			if (selected.systems || selected.knowledge) {
				progress = 20;
				await apiFetch('/setup/seed', {
					method: 'POST',
					body: JSON.stringify({ domain: 'banking' })
				});
				progress = 70;
			}

			// Seed platform docs as a bonus
			try {
				await apiFetch('/setup/seed', {
					method: 'POST',
					body: JSON.stringify({ domain: 'platform-docs' })
				});
			} catch {
				// Non-fatal: platform docs are a bonus
			}

			progress = 100;
			seeded = true;
			onNext({ sample_data: true });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to seed sample data.';
			progress = 0;
		} finally {
			seeding = false;
		}
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Sample Data</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Optionally load demo data to explore Firefly Desk right away.
	</p>

	<div class="mt-6 space-y-3">
		{#each categories as category}
			<label
				class="flex cursor-pointer items-start gap-4 rounded-lg border px-5 py-4 transition-all
					{category.disabled
					? 'cursor-not-allowed border-border opacity-60'
					: selected[category.id]
						? 'border-ember bg-ember/5'
						: 'border-border hover:border-text-secondary/40'}"
			>
				<input
					type="checkbox"
					checked={selected[category.id]}
					disabled={category.disabled || seeded}
					onchange={() => {
						if (!category.disabled) {
							selected = { ...selected, [category.id]: !selected[category.id] };
						}
					}}
					class="mt-0.5 accent-amber-500"
				/>
				<div class="flex-1">
					<div class="flex items-center gap-2">
						<span class="text-sm font-semibold text-text-primary">{category.label}</span>
						{#if category.comingSoon}
							<span
								class="inline-flex items-center gap-1 rounded-full bg-surface-hover px-2 py-0.5 text-[10px] font-medium text-text-secondary"
							>
								<Lock size={10} />
								Coming soon
							</span>
						{/if}
						{#if seeded && selected[category.id] && !category.disabled}
							<CheckCircle size={16} class="text-success" />
						{/if}
					</div>
					<p class="mt-1 text-xs text-text-secondary">{category.description}</p>
				</div>
			</label>
		{/each}
	</div>

	<!-- Progress bar during seeding -->
	{#if seeding}
		<div class="mt-5">
			<div class="mb-2 flex items-center gap-2 text-sm text-text-secondary">
				<Loader2 size={16} class="animate-spin" />
				<span>Seeding data...</span>
			</div>
			<div class="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
				<div
					class="h-full rounded-full bg-ember transition-all duration-500"
					style="width: {progress}%"
				></div>
			</div>
		</div>
	{/if}

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
