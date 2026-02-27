<!--
  User Agent Personality - Allows users to personalise the agent's
  personality, tone, greeting, and language. Admin settings act as
  defaults; admin can disable user overrides entirely.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, Save, RotateCcw, Info, Bot } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import { userSettings, loadUserSettings, saveUserSettings, updateSettings } from '$lib/stores/settings.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface PersonalityData {
		allow_user_personality_overrides: boolean;
		admin_defaults: {
			personality: string | null;
			tone: string | null;
			greeting: string | null;
			language: string | null;
		};
		user_overrides: {
			personality: string | null;
			tone: string | null;
			greeting: string | null;
			language: string | null;
		};
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const TONE_PRESETS = ['friendly', 'professional', 'casual', 'formal', 'custom'] as const;

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
	// State
	// -----------------------------------------------------------------------

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');
	let overridesAllowed = $state(true);

	let adminDefaults = $state({
		personality: '',
		tone: '',
		greeting: '',
		language: 'en'
	});

	let form = $state({
		personality: '' as string | null,
		tone: '' as string | null,
		greeting: '' as string | null,
		language: '' as string | null
	});

	let tonePreset = $state<string>('custom');

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadData() {
		loading = true;
		error = '';
		try {
			const data = await apiJson<PersonalityData>('/settings/user/agent-personality');
			overridesAllowed = data.allow_user_personality_overrides;
			adminDefaults = {
				personality: data.admin_defaults.personality || '',
				tone: data.admin_defaults.tone || '',
				greeting: data.admin_defaults.greeting || '',
				language: data.admin_defaults.language || 'en'
			};
			form = {
				personality: data.user_overrides.personality,
				tone: data.user_overrides.tone,
				greeting: data.user_overrides.greeting,
				language: data.user_overrides.language
			};
			syncTonePreset(form.tone || adminDefaults.tone);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load personality settings';
		} finally {
			loading = false;
		}
	}

	function syncTonePreset(tone: string) {
		const match = TONE_PRESETS.find((p) => p !== 'custom' && p === tone);
		tonePreset = match ?? 'custom';
	}

	$effect(() => {
		loadData();
	});

	// -----------------------------------------------------------------------
	// Save
	// -----------------------------------------------------------------------

	async function savePersonality() {
		saving = true;
		error = '';
		successMsg = '';
		try {
			updateSettings({
				agentPersonality: form.personality || null,
				agentTone: form.tone || null,
				agentGreeting: form.greeting || null,
				agentLanguage: form.language || null
			});
			await saveUserSettings();
			successMsg = 'Personality settings saved. Changes apply to your next conversation.';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save personality settings';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Reset helpers
	// -----------------------------------------------------------------------

	function resetField(field: 'personality' | 'tone' | 'greeting' | 'language') {
		form[field] = null;
		if (field === 'tone') {
			syncTonePreset(adminDefaults.tone);
		}
	}

	function resetAll() {
		form = { personality: null, tone: null, greeting: null, language: null };
		syncTonePreset(adminDefaults.tone);
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
</script>

<div class="flex h-full flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Agent Personality</h1>
			<p class="text-sm text-text-secondary">
				Personalise how the assistant communicates with you
			</p>
		</div>
		{#if overridesAllowed && !loading}
			<div class="flex items-center gap-2">
				<button
					type="button"
					onclick={resetAll}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<RotateCcw size={14} />
					Reset All
				</button>
				<button
					type="button"
					onclick={savePersonality}
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
		{/if}
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Success banner -->
	{#if successMsg}
		<div class="rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success">
			{successMsg}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if !overridesAllowed}
		<!-- Overrides disabled banner -->
		<div class="mx-auto max-w-lg rounded-xl border border-border bg-surface p-8 text-center">
			<Bot size={40} class="mx-auto mb-3 text-text-secondary/40" />
			<h2 class="text-base font-semibold text-text-primary">Personalisation Disabled</h2>
			<p class="mt-1 text-sm text-text-secondary">
				Your administrator has disabled user-level personality overrides. The agent
				will use the organisation-wide personality settings.
			</p>
			<p class="mt-3 text-xs text-text-secondary/60">
				Contact your administrator if you'd like this feature enabled.
			</p>
		</div>
	{:else}
		<div class="mx-auto w-full max-w-2xl space-y-6">
			<!-- Personality -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
						<Bot size={16} class="text-ember" />
						Personality
					</h2>
					{#if form.personality !== null}
						<button
							type="button"
							onclick={() => resetField('personality')}
							class="text-xs text-accent hover:underline"
						>
							Reset to default
						</button>
					{/if}
				</div>
				<textarea
					bind:value={form.personality}
					placeholder={adminDefaults.personality || 'Describe the personality...'}
					rows={3}
					class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent {form.personality === null ? 'text-text-secondary' : ''}"
				></textarea>
				<p class="mt-1 text-xs text-text-secondary">
					Describe how the assistant should behave — e.g. "warm, concise, and action-oriented"
				</p>
			</section>

			<!-- Tone -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-sm font-semibold text-text-primary">Tone</h2>
					{#if form.tone !== null}
						<button
							type="button"
							onclick={() => resetField('tone')}
							class="text-xs text-accent hover:underline"
						>
							Reset to default
						</button>
					{/if}
				</div>
				<div class="flex flex-col gap-2">
					<select
						value={tonePreset}
						onchange={(e) => handleToneChange(e.currentTarget.value)}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
					>
						{#each TONE_PRESETS as preset}
							<option value={preset}>
								{preset === 'custom' ? 'Custom' : preset.charAt(0).toUpperCase() + preset.slice(1)}
							</option>
						{/each}
					</select>
					{#if tonePreset === 'custom'}
						<input
							type="text"
							bind:value={form.tone}
							placeholder={adminDefaults.tone || 'Describe the desired tone...'}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						/>
					{/if}
				</div>
				<p class="mt-2 text-xs text-text-secondary">
					Default: <span class="font-medium">{adminDefaults.tone || 'not set'}</span>
				</p>
			</section>

			<!-- Greeting -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-sm font-semibold text-text-primary">Greeting Message</h2>
					{#if form.greeting !== null}
						<button
							type="button"
							onclick={() => resetField('greeting')}
							class="text-xs text-accent hover:underline"
						>
							Reset to default
						</button>
					{/if}
				</div>
				<input
					type="text"
					bind:value={form.greeting}
					placeholder={adminDefaults.greeting || 'Enter a greeting message...'}
					class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
				/>
				<p class="mt-1 text-xs text-text-secondary">
					Use <code class="rounded bg-surface-secondary px-1 py-0.5 text-xs">{'{name}'}</code> as a placeholder for your display name.
					Default: <span class="font-medium">{adminDefaults.greeting || 'not set'}</span>
				</p>
			</section>

			<!-- Language -->
			<section class="rounded-lg border border-border bg-surface p-5">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-sm font-semibold text-text-primary">Language</h2>
					{#if form.language !== null}
						<button
							type="button"
							onclick={() => resetField('language')}
							class="text-xs text-accent hover:underline"
						>
							Reset to default
						</button>
					{/if}
				</div>
				<select
					bind:value={form.language}
					class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none transition-colors focus:border-accent"
				>
					<option value={null}>Default ({LANGUAGES.find((l) => l.code === adminDefaults.language)?.label ?? adminDefaults.language})</option>
					{#each LANGUAGES as lang}
						<option value={lang.code}>{lang.label} ({lang.code})</option>
					{/each}
				</select>
			</section>

			<!-- Info -->
			<div class="flex items-start gap-2 rounded-lg border border-accent/20 bg-accent/5 px-4 py-3">
				<Info size={14} class="mt-0.5 shrink-0 text-accent/70" />
				<p class="text-xs text-accent/80">
					Your personality settings override the organisation defaults set by your administrator.
					Changes apply to new conversations. Use "Reset to default" to fall back to admin settings.
				</p>
			</div>
		</div>
	{/if}
</div>
