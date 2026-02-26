<!--
  AgentSetupStep.svelte -- Agent customization step of the setup wizard.

  Allows configuring the agent's name, personality preset, avatar URL,
  and greeting message. Includes an optional web search configuration
  section. Shows a live preview of how the agent would greet the user.
  Settings are passed through to the wizard's configure call.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		ArrowLeft,
		ArrowRight,
		ChevronDown,
		ChevronRight,
		Loader2,
		CheckCircle,
		XCircle,
		Eye,
		EyeOff
	} from 'lucide-svelte';
	import EmberAvatar from '$lib/components/chat/EmberAvatar.svelte';
	import { apiJson } from '$lib/services/api.js';

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
	let avatarLoadFailed = $state(false);
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

	// -----------------------------------------------------------------------
	// State -- Web Search
	// -----------------------------------------------------------------------

	let showSearchConfig = $state(false);
	let searchProvider = $state('');
	let searchApiKey = $state('');
	let showSearchKey = $state(false);
	let searchMaxResults = $state(5);
	let searchTesting = $state(false);
	let searchTestResult = $state<'success' | 'failure' | null>(null);
	let searchTestMessage = $state('');

	async function testSearchConnection() {
		if (!searchProvider || !searchApiKey) return;
		searchTesting = true;
		searchTestResult = null;
		searchTestMessage = '';
		try {
			const result = await apiJson<{
				success: boolean;
				result_count?: number;
				error?: string;
			}>('/settings/search/test', {
				method: 'POST',
				body: JSON.stringify({
					search_provider: searchProvider,
					search_api_key: searchApiKey,
					search_max_results: searchMaxResults
				})
			});
			if (result.success) {
				searchTestResult = 'success';
				searchTestMessage = `Search working (${result.result_count ?? 0} results)`;
			} else {
				searchTestResult = 'failure';
				searchTestMessage = result.error ?? 'Search test failed.';
			}
		} catch (e) {
			searchTestResult = 'failure';
			searchTestMessage = e instanceof Error ? e.message : 'Test failed.';
		} finally {
			searchTesting = false;
		}
	}

	// Reset avatar error state when URL changes
	$effect(() => {
		avatarUrl;
		avatarLoadFailed = false;
	});

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
		const data: Record<string, unknown> = {
			agent_settings: {
				name: agentName || 'Ember',
				display_name: displayName || agentName || 'Ember',
				personality: effectivePersonality || 'warm, professional, knowledgeable',
				tone: effectiveTone || 'friendly',
				greeting: greeting || "Hello! I'm {name}, your intelligent assistant.",
				avatar_url: avatarUrl
			}
		};
		if (searchProvider && searchApiKey) {
			data.search_config = {
				search_provider: searchProvider,
				search_api_key: searchApiKey,
				search_max_results: searchMaxResults
			};
		}
		onNext(data);
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
					{#if avatarUrl && !avatarLoadFailed}
						<img
							src={avatarUrl}
							alt={displayName || agentName}
							class="h-full w-full object-cover"
							onerror={() => { avatarLoadFailed = true; }}
						/>
					{:else}
						<EmberAvatar size={40} />
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
					{#if avatarUrl && !avatarLoadFailed}
						<img
							src={avatarUrl}
							alt={displayName || agentName}
							class="h-full w-full object-cover"
							onerror={() => { avatarLoadFailed = true; }}
						/>
					{:else}
						<EmberAvatar size={36} />
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

		<!-- Web Search (collapsible) -->
		<div>
			<button
				type="button"
				onclick={() => (showSearchConfig = !showSearchConfig)}
				class="flex w-full items-center gap-2 text-xs font-semibold tracking-wider text-text-secondary uppercase hover:text-text-primary"
			>
				{#if showSearchConfig}
					<ChevronDown size={14} />
				{:else}
					<ChevronRight size={14} />
				{/if}
				Web Search
				<span class="font-normal normal-case tracking-normal text-text-secondary/60">(optional)</span>
			</button>

			{#if showSearchConfig}
				<div class="mt-3 space-y-3 rounded-lg border border-border/50 bg-surface-hover/30 p-4">
					<p class="text-[11px] text-text-secondary">
						Enable web search so the agent can look up current information from the internet.
					</p>

					<!-- Provider -->
					<div>
						<label for="search-provider" class="mb-1.5 block text-xs font-medium text-text-secondary">
							Search Provider
						</label>
						<select
							id="search-provider"
							bind:value={searchProvider}
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
						>
							<option value="">None</option>
							<option value="tavily">Tavily</option>
						</select>
					</div>

					{#if searchProvider}
						<!-- API Key -->
						<div>
							<label for="search-api-key" class="mb-1.5 block text-xs font-medium text-text-secondary">
								API Key
							</label>
							<div class="relative">
								<input
									id="search-api-key"
									type={showSearchKey ? 'text' : 'password'}
									bind:value={searchApiKey}
									placeholder="tvly-..."
									autocomplete="off"
									class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
								/>
								<button
									type="button"
									onclick={() => (showSearchKey = !showSearchKey)}
									class="absolute top-1/2 right-2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
								>
									{#if showSearchKey}
										<EyeOff size={16} />
									{:else}
										<Eye size={16} />
									{/if}
								</button>
							</div>
						</div>

						<!-- Max Results -->
						<div>
							<label for="search-max" class="mb-1.5 block text-xs font-medium text-text-secondary">
								Max Results: {searchMaxResults}
							</label>
							<input
								id="search-max"
								type="range"
								min={1}
								max={10}
								bind:value={searchMaxResults}
								class="w-full accent-ember"
							/>
						</div>

						<!-- Test -->
						<button
							type="button"
							onclick={testSearchConnection}
							disabled={searchTesting || !searchApiKey}
							class="btn-hover inline-flex items-center gap-2 rounded-lg bg-ember px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
						>
							{#if searchTesting}
								<Loader2 size={16} class="animate-spin" />
								Testing...
							{:else}
								Test Search
							{/if}
						</button>

						{#if searchTestResult === 'success'}
							<div class="flex items-center gap-2 rounded-lg border border-success/30 bg-success/5 px-3 py-2 text-sm text-success">
								<CheckCircle size={16} />
								<span>{searchTestMessage}</span>
							</div>
						{:else if searchTestResult === 'failure'}
							<div class="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
								<XCircle size={16} />
								<span>{searchTestMessage}</span>
							</div>
						{/if}
					{/if}
				</div>
			{/if}
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
