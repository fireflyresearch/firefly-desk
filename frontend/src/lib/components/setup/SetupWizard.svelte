<!--
  SetupWizard.svelte -- Multi-step wizard shell for first-run configuration.

  Renders a progress rail on the left and the active step component on the
  right. Collects data from each step via onNext callbacks and aggregates
  it in a wizardData object.

  Steps:
    1. Welcome
    2. Database
    3. LLM Provider
    4. Embeddings (skipped if LLM is skipped)
    5. Agent Setup
    6. Admin User (prod only)
    7. Deployment
    8. SSO / OIDC (prod only)
    9. User Profile (dev mode only)
   10. Sample Data
   11. Ready

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Check } from 'lucide-svelte';
	import Logo from '$lib/components/layout/Logo.svelte';
	import WelcomeStep from './WelcomeStep.svelte';
	import DatabaseStep from './DatabaseStep.svelte';
	import LLMProviderStep from './LLMProviderStep.svelte';
	import EmbeddingStep from './EmbeddingStep.svelte';
	import AgentSetupStep from './AgentSetupStep.svelte';
	import AdminUserStep from './AdminUserStep.svelte';
	import DeploymentStep from './DeploymentStep.svelte';
	import SSOSetupStep from './SSOSetupStep.svelte';
	import UserProfileStep from './UserProfileStep.svelte';
	import SampleDataStep from './SampleDataStep.svelte';
	import ReadyStep from './ReadyStep.svelte';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface SetupWizardProps {
		status: Record<string, unknown> | null;
	}

	let { status }: SetupWizardProps = $props();

	// -----------------------------------------------------------------------
	// Step definitions
	// -----------------------------------------------------------------------

	interface StepDef {
		id: string;
		label: string;
		devOnly?: boolean;
		prodOnly?: boolean;
		skipWhenLlmSkipped?: boolean;
	}

	const allSteps: StepDef[] = [
		{ id: 'welcome', label: 'Welcome' },
		{ id: 'database', label: 'Database' },
		{ id: 'llm', label: 'LLM Provider' },
		{ id: 'embedding', label: 'Embeddings', skipWhenLlmSkipped: true },
		{ id: 'agent', label: 'Agent Setup' },
		{ id: 'admin', label: 'Admin User', prodOnly: true },
		{ id: 'deployment', label: 'Deployment' },
		{ id: 'sso', label: 'SSO / OIDC', prodOnly: true },
		{ id: 'profile', label: 'User Profile', devOnly: true },
		{ id: 'data', label: 'Sample Data' },
		{ id: 'ready', label: 'Ready' }
	];

	let isDevMode = $derived(status?.dev_mode === true);

	// Track whether LLM was skipped to conditionally skip embedding step
	let llmSkipped = $state(false);

	let steps = $derived(
		allSteps.filter((s) => {
			if (s.devOnly && !isDevMode) return false;
			if (s.prodOnly && isDevMode) return false;
			if (s.skipWhenLlmSkipped && llmSkipped) return false;
			return true;
		})
	);

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentIndex = $state(0);
	let wizardData = $state<Record<string, unknown>>({});

	let currentStep = $derived(steps[currentIndex]);

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	function handleNext(stepData?: Record<string, unknown>) {
		if (stepData) {
			wizardData = { ...wizardData, ...stepData };

			// Track whether the LLM provider was skipped
			if ('llm_provider' in stepData) {
				const wasSkipped = stepData.llm_provider === null;
				if (wasSkipped !== llmSkipped) {
					llmSkipped = wasSkipped;
					// Steps list will re-derive; currentIndex stays the same
					// which effectively advances past the now-removed embedding step
				}
			}
		}
		if (currentIndex < steps.length - 1) {
			currentIndex++;
		}
	}

	function handleBack() {
		if (currentIndex > 0) {
			currentIndex--;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-surface p-4">
	<div
		class="flex w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-surface-elevated shadow-lg"
	>
		<div class="flex flex-1">
			<!-- Progress rail (hidden on small screens) -->
			<nav
				class="hidden w-56 shrink-0 border-r border-border bg-surface-secondary p-6 sm:block"
				aria-label="Setup progress"
			>
				<Logo class="h-8 mb-4" />
				<h2 class="mb-6 text-xs font-semibold tracking-wider text-text-secondary uppercase">
					Setup
				</h2>
				<ol class="space-y-1">
					{#each steps as step, i}
						{@const isCompleted = i < currentIndex}
						{@const isCurrent = i === currentIndex}
						<li>
							<div
								class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors
									{isCurrent
									? 'bg-ember/10 font-medium text-ember'
									: isCompleted
										? 'text-text-primary'
										: 'text-text-secondary'}"
							>
								<!-- Step indicator -->
								<span
									class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold
										{isCurrent
										? 'bg-ember text-white'
										: isCompleted
											? 'bg-success/15 text-success'
											: 'bg-surface-hover text-text-secondary'}"
								>
									{#if isCompleted}
										<Check size={14} />
									{:else}
										{i + 1}
									{/if}
								</span>
								<span>{step.label}</span>
							</div>
						</li>
					{/each}
				</ol>
			</nav>

			<!-- Step content area -->
			<div class="flex min-h-[520px] flex-1 flex-col">
				<!-- Mobile step indicator -->
				<div class="border-b border-border px-6 py-3 text-xs text-text-secondary sm:hidden">
					Step {currentIndex + 1} of {steps.length}: {currentStep?.label}
				</div>

				<div class="flex-1 p-6 sm:p-8">
					{#if currentStep?.id === 'welcome'}
						<WelcomeStep {status} onNext={handleNext} />
					{:else if currentStep?.id === 'database'}
						<DatabaseStep {status} onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'llm'}
						<LLMProviderStep {status} onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'embedding'}
						<EmbeddingStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'agent'}
						<AgentSetupStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'admin'}
						<AdminUserStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'deployment'}
						<DeploymentStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'sso'}
						<SSOSetupStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'profile'}
						<UserProfileStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'data'}
						<SampleDataStep onNext={handleNext} onBack={handleBack} />
					{:else if currentStep?.id === 'ready'}
						<ReadyStep {wizardData} onBack={handleBack} />
					{/if}
				</div>
			</div>
		</div>

		<footer class="border-t border-border px-6 py-3 text-center text-xs text-text-secondary">
			&copy; 2026 Firefly Software Solutions Inc. &mdash; Licensed under the
			<a href="https://www.apache.org/licenses/LICENSE-2.0" target="_blank" rel="noopener" class="underline hover:text-text-primary">Apache License 2.0</a>
		</footer>
	</div>
</div>
