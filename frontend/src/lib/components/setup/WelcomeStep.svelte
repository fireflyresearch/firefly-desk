<!--
  WelcomeStep.svelte -- First step of the setup wizard.

  Shows a greeting from Ember, environment info cards (mode, database, agent),
  and a "Get Started" button to advance to the next step.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Monitor, Database, Flame } from 'lucide-svelte';
	import EmberAvatar from '$lib/components/chat/EmberAvatar.svelte';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface WelcomeStepProps {
		status: Record<string, unknown> | null;
		onNext: (data?: Record<string, unknown>) => void;
	}

	let { status, onNext }: WelcomeStepProps = $props();

	// -----------------------------------------------------------------------
	// Derived values from the SetupStatus API response
	// -----------------------------------------------------------------------

	let appTitle = $derived((status?.app_title as string) ?? 'Firefly Desk');
	let devMode = $derived(status?.dev_mode === true);
	let databaseType = $derived((status?.database_type as string) ?? (status?.database_configured ? 'postgresql' : 'sqlite'));
	let agentName = $derived((status?.agent_name as string) ?? 'Ember');
	let appVersion = $derived((status?.app_version as string) ?? '');

	interface InfoCard {
		icon: typeof Monitor;
		label: string;
		value: string;
		accent?: boolean;
	}

	let infoCards: InfoCard[] = $derived([
		{
			icon: Monitor,
			label: 'Mode',
			value: devMode ? 'Development' : 'Production'
		},
		{
			icon: Database,
			label: 'Database',
			value: databaseType === 'postgresql' ? 'PostgreSQL' : 'SQLite'
		},
		{
			icon: Flame,
			label: 'Agent',
			value: appVersion ? `${agentName} v${appVersion}` : agentName,
			accent: true
		}
	]);
</script>

<div class="flex h-full flex-col items-center justify-center text-center">
	<!-- Ember greeting -->
	<div class="mb-6">
		<EmberAvatar size={64} />
	</div>

	<h1 class="text-2xl font-bold text-text-primary">Welcome to {appTitle}</h1>
	<p class="mt-2 text-sm text-text-secondary">
		Let's configure your instance. This takes about 2 minutes.
	</p>

	<!-- Info cards -->
	<div class="mt-8 grid w-full max-w-md grid-cols-3 gap-3">
		{#each infoCards as card}
			<div
				class="flex flex-col items-center gap-2 rounded-lg border border-border bg-surface-secondary p-4"
			>
				<div
					class="flex h-8 w-8 items-center justify-center rounded-lg
						{card.accent ? 'bg-ember/10 text-ember' : 'bg-surface-hover text-text-secondary'}"
				>
					<card.icon size={16} />
				</div>
				<span class="text-[11px] font-medium tracking-wide text-text-secondary uppercase">
					{card.label}
				</span>
				<span class="text-sm font-semibold text-text-primary">{card.value}</span>
			</div>
		{/each}
	</div>

	<!-- CTA -->
	<button
		type="button"
		onclick={() => onNext()}
		class="btn-hover mt-10 rounded-lg bg-ember px-8 py-2.5 text-sm font-semibold text-white shadow-sm"
	>
		Get Started
	</button>
</div>
