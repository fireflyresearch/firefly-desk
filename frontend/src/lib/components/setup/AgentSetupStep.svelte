<!--
  AgentSetupStep.svelte -- Agent customization step of the setup wizard.

  Allows configuring the agent's name, personality preset, avatar URL,
  and greeting message. Shows a live preview of how the agent would greet
  the user. Settings are passed through to the wizard's configure call.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight } from 'lucide-svelte';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface AgentSetupStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: AgentSetupStepProps = $props();

	// -----------------------------------------------------------------------
	// Personality presets
	// -----------------------------------------------------------------------

	interface PersonalityPreset {
		id: string;
		label: string;
		personality: string;
		tone: string;
	}

	const presets: PersonalityPreset[] = [
		{
			id: 'warm',
			label: 'Warm & Friendly',
			personality: 'warm, professional, knowledgeable',
			tone: 'friendly'
		},
		{
			id: 'professional',
			label: 'Professional & Concise',
			personality: 'efficient, precise, direct',
			tone: 'professional'
		},
		{
			id: 'casual',
			label: 'Casual & Playful',
			personality: 'cheerful, approachable, casual',
			tone: 'casual'
		},
		{
			id: 'custom',
			label: 'Custom',
			personality: '',
			tone: 'custom'
		}
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let agentName = $state('Ember');
	let displayName = $state('Ember');
	let selectedPreset = $state('warm');
	let customPersonality = $state('');
	let avatarUrl = $state('');
	let greeting = $state("Hello! I'm {name}, your intelligent assistant.");

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let currentPreset = $derived(presets.find((p) => p.id === selectedPreset) ?? presets[0]);
	let isCustom = $derived(selectedPreset === 'custom');

	let effectivePersonality = $derived(
		isCustom ? customPersonality : currentPreset.personality
	);
	let effectiveTone = $derived(isCustom ? 'custom' : currentPreset.tone);

	/** Greeting with {name} replaced for the live preview. */
	let previewGreeting = $derived(greeting.replace(/\{name\}/g, displayName || agentName));

	/** Initials for the avatar fallback. */
	let initials = $derived(
		(displayName || agentName || 'E')
			.split(/\s+/)
			.map((w: string) => w[0])
			.join('')
			.toUpperCase()
			.slice(0, 2)
	);

	// Keep display_name in sync with name by default
	let nameManuallyEdited = $state(false);

	function handleNameChange(event: Event) {
		const input = event.target as HTMLInputElement;
		agentName = input.value;
		if (!nameManuallyEdited) {
			displayName = input.value;
		}
	}

	function handleDisplayNameChange(event: Event) {
		const input = event.target as HTMLInputElement;
		displayName = input.value;
		nameManuallyEdited = true;
	}

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleContinue() {
		onNext({
			agent_settings: {
				name: agentName || 'Ember',
				display_name: displayName || agentName || 'Ember',
				personality: effectivePersonality || 'warm, professional, knowledgeable',
				tone: effectiveTone || 'friendly',
				greeting: greeting || "Hello! I'm {name}, your intelligent assistant.",
				avatar_url: avatarUrl
			}
		});
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Agent Setup</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Customize your AI assistant's identity and personality.
	</p>

	<div class="mt-5 flex-1 space-y-5 overflow-y-auto pr-1">
		<!-- Agent name -->
		<div class="grid grid-cols-2 gap-4">
			<div>
				<label for="agent-name" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Agent Name
				</label>
				<input
					id="agent-name"
					type="text"
					value={agentName}
					oninput={handleNameChange}
					placeholder="Ember"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>
			<div>
				<label
					for="display-name"
					class="mb-1.5 block text-xs font-medium text-text-secondary"
				>
					Display Name
				</label>
				<input
					id="display-name"
					type="text"
					value={displayName}
					oninput={handleDisplayNameChange}
					placeholder="Ember"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>
		</div>

		<!-- Personality presets -->
		<div>
			<span class="mb-2 block text-xs font-medium text-text-secondary">Personality</span>
			<div class="grid grid-cols-2 gap-2">
				{#each presets as preset}
					<button
						type="button"
						onclick={() => (selectedPreset = preset.id)}
						class="rounded-lg border px-3 py-2.5 text-left transition-all
							{selectedPreset === preset.id
							? 'border-ember bg-ember/5 shadow-sm'
							: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
					>
						<span
							class="block text-sm font-medium {selectedPreset === preset.id
								? 'text-ember'
								: 'text-text-primary'}">{preset.label}</span
						>
						{#if preset.id !== 'custom'}
							<span class="mt-0.5 block text-[11px] text-text-secondary">
								{preset.personality}
							</span>
						{:else}
							<span class="mt-0.5 block text-[11px] text-text-secondary">
								Define your own personality
							</span>
						{/if}
					</button>
				{/each}
			</div>

			<!-- Custom personality textarea -->
			{#if isCustom}
				<textarea
					bind:value={customPersonality}
					placeholder="e.g., thoughtful, empathetic, detail-oriented"
					rows={2}
					class="mt-3 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				></textarea>
			{/if}
		</div>

		<!-- Avatar URL -->
		<div>
			<label for="avatar-url" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Avatar URL <span class="text-text-secondary/60">(optional)</span>
			</label>
			<div class="flex items-center gap-3">
				<input
					id="avatar-url"
					type="url"
					bind:value={avatarUrl}
					placeholder="https://example.com/avatar.png"
					class="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
				<!-- Live circular preview -->
				<div
					class="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-ember/10"
				>
					{#if avatarUrl}
						<img
							src={avatarUrl}
							alt={displayName || agentName}
							class="h-full w-full object-cover"
							onerror={(e) => {
								const img = e.currentTarget as HTMLImageElement;
								img.style.display = 'none';
								const parent = img.parentElement;
								if (parent) {
									const fallback = parent.querySelector('.avatar-fallback');
									if (fallback instanceof HTMLElement) fallback.style.display = 'flex';
								}
							}}
						/>
						<span
							class="avatar-fallback hidden h-full w-full items-center justify-center text-xs font-semibold text-ember"
						>
							{initials}
						</span>
					{:else}
						<span class="text-xs font-semibold text-ember">{initials}</span>
					{/if}
				</div>
			</div>
		</div>

		<!-- Greeting -->
		<div>
			<label for="greeting" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Greeting <span class="text-text-secondary/60">(use {'{name}'} as a placeholder)</span>
			</label>
			<input
				id="greeting"
				type="text"
				bind:value={greeting}
				placeholder="Hello! I'm {'{name}'}, your intelligent assistant."
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
		</div>

		<!-- Live preview card -->
		<div class="rounded-lg border border-border bg-surface-secondary p-4">
			<span class="mb-2 block text-[11px] font-semibold tracking-wider text-text-secondary uppercase">
				Preview
			</span>
			<div class="flex items-start gap-3">
				<div
					class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-ember/10"
				>
					{#if avatarUrl}
						<img
							src={avatarUrl}
							alt={displayName || agentName}
							class="h-full w-full object-cover"
							onerror={(e) => {
								const img = e.currentTarget as HTMLImageElement;
								img.style.display = 'none';
							}}
						/>
					{:else}
						<span class="text-xs font-semibold text-ember">{initials}</span>
					{/if}
				</div>
				<div>
					<span class="block text-sm font-semibold text-text-primary">
						{displayName || agentName || 'Ember'}
					</span>
					<p class="mt-0.5 text-sm text-text-secondary">{previewGreeting}</p>
				</div>
			</div>
		</div>
	</div>

	<!-- Navigation -->
	<div class="mt-6 flex items-center justify-between border-t border-border pt-4">
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
