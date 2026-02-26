<!--
  DataImportStep.svelte -- Choose how to populate data during setup.

  Presents three options: import your own data (cloud sources / file
  upload after setup), use sample demo data, or skip data entirely.
  The choice controls whether the SampleDataStep seeds demo content.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight, Upload, Database, SkipForward } from 'lucide-svelte';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface DataImportStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: DataImportStepProps = $props();

	// -----------------------------------------------------------------------
	// Options
	// -----------------------------------------------------------------------

	type DataChoice = 'import' | 'sample' | 'skip';

	interface DataOption {
		id: DataChoice;
		label: string;
		description: string;
		detail: string;
	}

	const options: DataOption[] = [
		{
			id: 'import',
			label: 'Import My Data',
			description: 'Connect cloud sources or upload files after setup.',
			detail:
				'You can connect S3, Azure Blob, Google Drive, SharePoint, and more from the Knowledge Base Manager once setup is complete.'
		},
		{
			id: 'sample',
			label: 'Use Sample Data',
			description: 'Load demo banking data to explore features.',
			detail:
				'Includes sample systems, API catalog, knowledge documents, and business processes. Great for evaluating Firefly Desk.'
		},
		{
			id: 'skip',
			label: 'Skip for Now',
			description: 'Start with an empty instance.',
			detail:
				'You can import data or load samples later from the Admin console.'
		}
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let selected = $state<DataChoice>('sample');

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleContinue() {
		onNext({ data_choice: selected });
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Data Setup</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Choose how to populate your instance with data.
	</p>

	<div class="mt-6 space-y-3">
		{#each options as option}
			{@const isSelected = selected === option.id}
			<button
				type="button"
				onclick={() => (selected = option.id)}
				class="flex w-full items-start gap-4 rounded-lg border px-5 py-4 text-left transition-all
					{isSelected
					? 'border-ember bg-ember/5 shadow-sm'
					: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
			>
				<div
					class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full
						{isSelected ? 'bg-ember/15 text-ember' : 'bg-surface-hover text-text-secondary'}"
				>
					{#if option.id === 'import'}
						<Upload size={16} />
					{:else if option.id === 'sample'}
						<Database size={16} />
					{:else}
						<SkipForward size={16} />
					{/if}
				</div>
				<div class="flex-1">
					<span
						class="block text-sm font-semibold {isSelected ? 'text-ember' : 'text-text-primary'}"
					>
						{option.label}
					</span>
					<p class="mt-0.5 text-xs text-text-secondary">{option.description}</p>
					{#if isSelected}
						<p class="mt-2 text-[11px] leading-relaxed text-text-secondary/80">
							{option.detail}
						</p>
					{/if}
				</div>
				<div class="mt-1 shrink-0">
					<div
						class="flex h-5 w-5 items-center justify-center rounded-full border-2 transition-colors
							{isSelected ? 'border-ember' : 'border-border'}"
					>
						{#if isSelected}
							<div class="h-2.5 w-2.5 rounded-full bg-ember"></div>
						{/if}
					</div>
				</div>
			</button>
		{/each}
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
