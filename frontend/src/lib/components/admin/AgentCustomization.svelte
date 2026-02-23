<!--
  AgentCustomization.svelte - Admin panel for customising the assistant identity.

  Allows administrators to configure the agent name, avatar, personality,
  tone, greeting message, behaviour rules, custom instructions, and language.
  Includes a live preview card showing how the agent will introduce itself.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Save,
		Loader2,
		RotateCcw,
		Bot,
		Plus,
		X,
		GripVertical,
		ArrowUp,
		ArrowDown,
		Eye
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import {
		agentSettings,
		loadAgentSettings,
		AGENT_DEFAULTS,
		type AgentSettings
	} from '$lib/stores/agent.js';
	import EmberAvatar from '$lib/components/chat/EmberAvatar.svelte';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');

	let form = $state<AgentSettings>({ ...AGENT_DEFAULTS });
	let newRule = $state('');
	let avatarError = $state(false);

	// Tone presets -- "custom" means the user typed something freeform.
	const TONE_PRESETS = [
		'friendly yet precise',
		'professional',
		'casual',
		'formal',
		'empathetic',
		'custom'
	] as const;

	let tonePreset = $state<string>('friendly yet precise');

	// Language options
	const LANGUAGES = [
		{ code: 'en', label: 'English' },
		{ code: 'es', label: 'Spanish' },
		{ code: 'fr', label: 'French' },
		{ code: 'de', label: 'German' },
		{ code: 'pt', label: 'Portuguese' },
		{ code: 'it', label: 'Italian' },
		{ code: 'nl', label: 'Dutch' },
		{ code: 'ja', label: 'Japanese' },
		{ code: 'ko', label: 'Korean' },
		{ code: 'zh', label: 'Chinese' },
		{ code: 'ar', label: 'Arabic' },
		{ code: 'hi', label: 'Hindi' }
	];

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	/** Preview greeting with {name} replaced by the current display name. */
	let previewGreeting = $derived(
		form.greeting.replace(/\{name\}/g, form.display_name || form.name)
	);

	/** Initials for the avatar fallback. */
	let avatarInitials = $derived(
		(form.display_name || form.name)
			.split(' ')
			.map((p) => p[0])
			.join('')
			.toUpperCase()
			.slice(0, 2)
	);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadSettings() {
		loading = true;
		error = '';
		try {
			const data = await loadAgentSettings(true);
			form = { ...data };
			syncTonePreset(data.tone);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load agent settings';
		} finally {
			loading = false;
		}
	}

	function syncTonePreset(tone: string) {
		const match = TONE_PRESETS.find((p) => p !== 'custom' && p === tone);
		tonePreset = match ?? 'custom';
	}

	$effect(() => {
		loadSettings();
	});

	// -----------------------------------------------------------------------
	// Save
	// -----------------------------------------------------------------------

	async function saveSettings() {
		saving = true;
		error = '';
		successMsg = '';
		try {
			const payload: AgentSettings = { ...form };
			await apiJson('/settings/agent', {
				method: 'PUT',
				body: JSON.stringify(payload)
			});
			agentSettings.set({ ...payload });
			successMsg = 'Agent settings saved successfully.';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save agent settings';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Reset to defaults
	// -----------------------------------------------------------------------

	function resetToDefaults() {
		form = { ...AGENT_DEFAULTS };
		syncTonePreset(AGENT_DEFAULTS.tone);
		avatarError = false;
	}

	// -----------------------------------------------------------------------
	// Behaviour rules
	// -----------------------------------------------------------------------

	function addRule() {
		const rule = newRule.trim();
		if (!rule) return;
		form.behavior_rules = [...form.behavior_rules, rule];
		newRule = '';
	}

	function removeRule(index: number) {
		form.behavior_rules = form.behavior_rules.filter((_, i) => i !== index);
	}

	function moveRule(index: number, direction: -1 | 1) {
		const target = index + direction;
		if (target < 0 || target >= form.behavior_rules.length) return;
		const rules = [...form.behavior_rules];
		[rules[index], rules[target]] = [rules[target], rules[index]];
		form.behavior_rules = rules;
	}

	// -----------------------------------------------------------------------
	// Tone preset handler
	// -----------------------------------------------------------------------

	function handleToneChange(preset: string) {
		tonePreset = preset;
		if (preset !== 'custom') {
			form.tone = preset;
		}
	}

	// -----------------------------------------------------------------------
	// Avatar validation
	// -----------------------------------------------------------------------

	function handleAvatarLoad() {
		avatarError = false;
	}

	function handleAvatarError() {
		avatarError = true;
	}
</script>

<div class="flex h-full flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Agent Customization</h1>
			<p class="text-sm text-text-secondary">
				Configure the assistant identity, personality, and behaviour
			</p>
		</div>
		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={resetToDefaults}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			>
				<RotateCcw size={14} />
				Reset to Defaults
			</button>
			<button
				type="button"
				onclick={saveSettings}
				disabled={saving}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
			>
				{#if saving}
					<Loader2 size={14} class="animate-spin" />
				{:else}
					<Save size={14} />
				{/if}
				Save Changes
			</button>
		</div>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Success banner -->
	{#if successMsg}
		<div
			class="rounded-md border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success"
		>
			{successMsg}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
			<!-- Left column: form fields -->
			<div class="flex flex-col gap-6 lg:col-span-2">
				<!-- Identity section -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
						<Bot size={16} class="text-ember" />
						Identity
					</h2>

					<div class="flex flex-col gap-4">
						<div class="grid grid-cols-2 gap-4">
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Internal Name</span>
								<input
									type="text"
									bind:value={form.name}
									placeholder="Ember"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
								<span class="text-xs text-text-secondary">Used in system prompts and templates</span>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Display Name</span>
								<input
									type="text"
									bind:value={form.display_name}
									placeholder="Ember"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
								<span class="text-xs text-text-secondary">Shown to users in the interface</span>
							</label>
						</div>

						<!-- Avatar URL -->
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Avatar URL</span>
							<div class="flex items-center gap-3">
								<input
									type="url"
									bind:value={form.avatar_url}
									placeholder="https://example.com/avatar.png"
									class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
								<!-- Live avatar preview -->
								<div
									class="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-surface-secondary"
								>
									{#if form.avatar_url && !avatarError}
										<img
											src={form.avatar_url}
											alt={form.display_name}
											class="h-10 w-10 rounded-full object-cover"
											onload={handleAvatarLoad}
											onerror={handleAvatarError}
										/>
									{:else if form.avatar_url && avatarError}
										<span class="text-xs font-medium text-text-secondary">{avatarInitials}</span>
									{:else}
										<EmberAvatar size={24} />
									{/if}
								</div>
							</div>
							<span class="text-xs text-text-secondary">
								Leave empty to use the default Ember avatar. Supports PNG, JPG, SVG, or GIF.
							</span>
						</label>

						<!-- Language -->
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Language</span>
							<select
								bind:value={form.language}
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
							>
								{#each LANGUAGES as lang}
									<option value={lang.code}>{lang.label} ({lang.code})</option>
								{/each}
							</select>
						</label>
					</div>
				</section>

				<!-- Personality section -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<h2 class="mb-4 text-sm font-semibold text-text-primary">Personality</h2>

					<div class="flex flex-col gap-4">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Personality Description</span>
							<textarea
								bind:value={form.personality}
								rows={2}
								placeholder="warm, professional, knowledgeable"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
							></textarea>
							<span class="text-xs text-text-secondary">
								Brief keywords or description of the agent personality
							</span>
						</label>

						<!-- Tone -->
						<div class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Tone</span>
							<div class="flex flex-wrap gap-2">
								{#each TONE_PRESETS as preset}
									<button
										type="button"
										onclick={() => handleToneChange(preset)}
										class="rounded-md border px-3 py-1.5 text-sm transition-colors
											{tonePreset === preset
											? 'border-accent bg-accent/10 font-medium text-accent'
											: 'border-border text-text-secondary hover:bg-surface-hover hover:text-text-primary'}"
									>
										{preset === 'custom' ? 'Custom' : preset}
									</button>
								{/each}
							</div>
							{#if tonePreset === 'custom'}
								<input
									type="text"
									bind:value={form.tone}
									placeholder="Describe the desired tone..."
									class="mt-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
								/>
							{/if}
						</div>

						<!-- Greeting -->
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Greeting Message</span>
							<textarea
								bind:value={form.greeting}
								rows={2}
								placeholder="Hello! I'm {name}, your intelligent assistant."
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
							></textarea>
							<span class="text-xs text-text-secondary">
								Use <code class="rounded bg-surface-secondary px-1 py-0.5 text-xs">{'{name}'}</code> as
								a placeholder for the display name
							</span>
						</label>
					</div>
				</section>

				<!-- Behaviour rules section -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<h2 class="mb-4 text-sm font-semibold text-text-primary">Behaviour Rules</h2>
					<p class="mb-3 text-xs text-text-secondary">
						Ordered rules that guide agent responses. The agent will follow these in priority order.
					</p>

					{#if form.behavior_rules.length > 0}
						<ul class="mb-3 flex flex-col gap-1.5">
							{#each form.behavior_rules as rule, i}
								<li
									class="group flex items-center gap-2 rounded-md border border-border bg-surface-secondary px-3 py-2 text-sm text-text-primary"
								>
									<GripVertical size={14} class="shrink-0 text-text-secondary/50" />
									<span class="flex-1">{rule}</span>
									<div
										class="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100"
									>
										<button
											type="button"
											onclick={() => moveRule(i, -1)}
											disabled={i === 0}
											class="rounded p-0.5 text-text-secondary transition-colors hover:text-text-primary disabled:opacity-30"
											title="Move up"
										>
											<ArrowUp size={12} />
										</button>
										<button
											type="button"
											onclick={() => moveRule(i, 1)}
											disabled={i === form.behavior_rules.length - 1}
											class="rounded p-0.5 text-text-secondary transition-colors hover:text-text-primary disabled:opacity-30"
											title="Move down"
										>
											<ArrowDown size={12} />
										</button>
										<button
											type="button"
											onclick={() => removeRule(i)}
											class="rounded p-0.5 text-text-secondary transition-colors hover:text-danger"
											title="Remove"
										>
											<X size={12} />
										</button>
									</div>
								</li>
							{/each}
						</ul>
					{/if}

					<div class="flex gap-2">
						<input
							type="text"
							bind:value={newRule}
							placeholder="Add a behaviour rule..."
							onkeydown={(e) => {
								if (e.key === 'Enter') {
									e.preventDefault();
									addRule();
								}
							}}
							class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						/>
						<button
							type="button"
							onclick={addRule}
							class="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
						>
							<Plus size={14} />
							Add
						</button>
					</div>
				</section>

				<!-- Custom instructions section -->
				<section class="rounded-lg border border-border bg-surface p-5">
					<h2 class="mb-4 text-sm font-semibold text-text-primary">Custom Instructions</h2>
					<p class="mb-3 text-xs text-text-secondary">
						Advanced free-form instructions appended to the system prompt. For power users.
					</p>
					<textarea
						bind:value={form.custom_instructions}
						rows={6}
						placeholder="Enter custom system instructions..."
						class="w-full rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none transition-colors focus:border-accent"
					></textarea>
				</section>
			</div>

			<!-- Right column: live preview -->
			<div class="lg:col-span-1">
				<div class="sticky top-6">
					<section class="rounded-lg border border-border bg-surface p-5">
						<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
							<Eye size={16} class="text-ember" />
							Live Preview
						</h2>

						<!-- Agent card preview -->
						<div
							class="rounded-lg border border-border bg-surface-secondary p-4"
						>
							<!-- Avatar and name -->
							<div class="mb-3 flex items-center gap-3">
								<div
									class="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-ember/30 bg-ember/5"
								>
									{#if form.avatar_url && !avatarError}
										<img
											src={form.avatar_url}
											alt={form.display_name}
											class="h-12 w-12 rounded-full object-cover"
											onerror={handleAvatarError}
										/>
									{:else if form.avatar_url && avatarError}
										<span class="text-sm font-semibold text-ember">{avatarInitials}</span>
									{:else}
										<EmberAvatar size={28} />
									{/if}
								</div>
								<div>
									<p class="text-sm font-semibold text-text-primary">
										{form.display_name || form.name || 'Agent'}
									</p>
									<p class="text-xs text-text-secondary">
										{form.personality || 'No personality set'}
									</p>
								</div>
							</div>

							<!-- Greeting preview -->
							<div class="rounded-md border-l-2 border-l-ember/30 bg-surface pl-3 py-2 pr-2">
								<p class="text-sm leading-relaxed text-text-primary">
									{previewGreeting || 'No greeting configured.'}
								</p>
							</div>

							<!-- Metadata -->
							<div class="mt-3 flex flex-wrap gap-2">
								<span
									class="rounded-full border border-ember/20 bg-ember/5 px-2 py-0.5 text-xs text-ember"
								>
									{form.tone || 'no tone'}
								</span>
								<span
									class="rounded-full border border-border bg-surface px-2 py-0.5 text-xs text-text-secondary"
								>
									{LANGUAGES.find((l) => l.code === form.language)?.label ?? form.language}
								</span>
								{#if form.behavior_rules.length > 0}
									<span
										class="rounded-full border border-border bg-surface px-2 py-0.5 text-xs text-text-secondary"
									>
										{form.behavior_rules.length} rule{form.behavior_rules.length === 1 ? '' : 's'}
									</span>
								{/if}
							</div>
						</div>

						<!-- Chat bubble preview -->
						<div class="mt-4">
							<p class="mb-2 text-xs font-medium text-text-secondary">Chat Preview</p>
							<div class="flex items-start gap-2">
								<div
									class="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full"
								>
									{#if form.avatar_url && !avatarError}
										<img
											src={form.avatar_url}
											alt={form.display_name}
											class="h-7 w-7 rounded-full object-cover"
											onerror={handleAvatarError}
										/>
									{:else}
										<EmberAvatar size={20} />
									{/if}
								</div>
								<div class="rounded-lg border-l-2 border-l-ember/30 pl-3 text-sm leading-relaxed text-text-primary">
									{previewGreeting || 'Hello!'}
								</div>
							</div>
						</div>
					</section>
				</div>
			</div>
		</div>
	{/if}
</div>
