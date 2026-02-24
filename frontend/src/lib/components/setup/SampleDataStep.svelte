<!--
  SampleDataStep.svelte -- Optionally seed demo data for the instance.

  Offers checkboxes for different data categories: Systems & APIs,
  Knowledge Base docs, Skills, Knowledge Graph entities, and Business
  Processes. Shows a real-time progress bar via SSE during seeding.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight, CheckCircle, Loader2 } from 'lucide-svelte';
	import { apiFetch } from '$lib/services/api.js';
	import { parseSSEStream } from '$lib/services/sse.js';

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
	}

	const categories: SeedCategory[] = [
		{
			id: 'systems',
			label: 'Systems & APIs',
			description: '5 banking systems, 16 API endpoints, and integration metadata.',
			defaultOn: true
		},
		{
			id: 'knowledge',
			label: 'Knowledge Base',
			description: '5 knowledge documents covering banking policies, procedures, and FAQs.',
			defaultOn: true
		},
		{
			id: 'skills',
			label: 'Skills',
			description: 'Banking domain skills for automated task handling.',
			defaultOn: true
		},
		{
			id: 'knowledge_graph',
			label: 'Knowledge Graph',
			description: 'Entity and relationship data extracted via LLM analysis.',
			defaultOn: true
		},
		{
			id: 'processes',
			label: 'Business Processes',
			description: 'Auto-discovered business processes from catalog and knowledge.',
			defaultOn: true
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
	let currentPhase = $state('');
	let currentPhaseLabel = $state('');
	let currentMessage = $state('');
	let phaseErrors = $state<string[]>([]);

	let anythingSelected = $derived(
		Object.values(selected).some((on) => on)
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
		currentPhase = '';
		currentPhaseLabel = '';
		currentMessage = '';
		phaseErrors = [];

		try {
			const response = await apiFetch('/setup/seed', {
				method: 'POST',
				body: JSON.stringify({
					domain: 'banking',
					include_systems: selected.systems ?? true,
					include_knowledge: selected.knowledge ?? true,
					include_skills: selected.skills ?? true,
					include_kg: selected.knowledge_graph ?? true,
					include_discovery: selected.processes ?? true
				})
			});

			const contentType = response.headers.get('Content-Type') ?? '';

			if (contentType.includes('text/event-stream')) {
				await parseSSEStream(
					response,
					(msg) => {
						if (msg.event === 'seed_progress') {
							currentPhase = (msg.data.phase as string) ?? '';
							currentPhaseLabel = (msg.data.phase_label as string) ?? '';
							currentMessage = (msg.data.message as string) ?? '';
							progress = (msg.data.overall_progress as number) ?? 0;
							if (msg.data.error) {
								phaseErrors = [...phaseErrors, `${msg.data.phase_label}: ${msg.data.error}`];
							}
						} else if (msg.event === 'done') {
							progress = 100;
							seeded = true;
						}
					},
					(err) => {
						error = err.message;
					},
					() => {
						seeding = false;
						if (seeded) {
							onNext({ sample_data: true });
						}
					}
				);
			} else {
				// Fallback: non-streaming response (e.g. unseed or error)
				const result = await response.json();
				if (result.success) {
					progress = 100;
					seeded = true;
					onNext({ sample_data: true });
				} else {
					error = result.message || 'Seeding failed.';
				}
				seeding = false;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to seed sample data.';
			progress = 0;
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
					{selected[category.id]
					? 'border-ember bg-ember/5'
					: 'border-border hover:border-text-secondary/40'}"
			>
				<input
					type="checkbox"
					checked={selected[category.id]}
					disabled={seeded}
					onchange={() => {
						selected = { ...selected, [category.id]: !selected[category.id] };
					}}
					class="mt-0.5 accent-amber-500"
				/>
				<div class="flex-1">
					<div class="flex items-center gap-2">
						<span class="text-sm font-semibold text-text-primary">{category.label}</span>
						{#if seeded && selected[category.id]}
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
				<span>{currentPhaseLabel || 'Preparing...'}</span>
			</div>
			{#if currentMessage}
				<p class="mb-2 truncate text-xs text-text-secondary/70">{currentMessage}</p>
			{/if}
			<div class="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
				<div
					class="h-full rounded-full bg-ember transition-all duration-500"
					style="width: {progress}%"
				></div>
			</div>
			<p class="mt-1 text-right text-xs text-text-secondary">{progress}%</p>
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

	<!-- Phase warnings -->
	{#if phaseErrors.length > 0}
		<div class="mt-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-xs text-warning">
			{#each phaseErrors as warning}
				<p>{warning}</p>
			{/each}
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
			{:else if error}
				Retry
				<ArrowRight size={16} />
			{:else}
				Continue
				<ArrowRight size={16} />
			{/if}
		</button>
	</div>
</div>
