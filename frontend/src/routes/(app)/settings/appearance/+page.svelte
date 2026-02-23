<!--
  Settings appearance page - Theme and display preferences.

  Provides theme selection (light/dark/system) with visual previews.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, Palette } from 'lucide-svelte';
	import { themePreference, setTheme, type ThemePreference } from '$lib/stores/theme.js';
	import {
		userSettings,
		updateSettings,
		loadUserSettings,
		saveUserSettings
	} from '$lib/stores/settings.js';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let saving = $state(false);
	let saved = $state(false);
	let error = $state('');

	// -----------------------------------------------------------------------
	// Theme preview definitions
	// -----------------------------------------------------------------------

	const themeOptions: {
		value: ThemePreference;
		label: string;
		description: string;
		previewBg: string;
		previewHeader: string;
		previewSidebar: string;
		previewText: string;
	}[] = [
		{
			value: 'light',
			label: 'Light',
			description: 'Clean, bright interface',
			previewBg: 'bg-white',
			previewHeader: 'bg-gray-200',
			previewSidebar: 'bg-gray-100',
			previewText: 'bg-gray-300'
		},
		{
			value: 'dark',
			label: 'Dark',
			description: 'Easy on the eyes',
			previewBg: 'bg-gray-900',
			previewHeader: 'bg-gray-800',
			previewSidebar: 'bg-gray-800',
			previewText: 'bg-gray-600'
		},
		{
			value: 'system',
			label: 'System',
			description: 'Match your OS setting',
			previewBg: 'bg-gradient-to-r from-white to-gray-900',
			previewHeader: 'bg-gradient-to-r from-gray-200 to-gray-800',
			previewSidebar: 'bg-gradient-to-r from-gray-100 to-gray-800',
			previewText: 'bg-gradient-to-r from-gray-300 to-gray-600'
		}
	];

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	$effect(() => {
		loadUserSettings();
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleThemeChange(value: ThemePreference) {
		setTheme(value);
		updateSettings({ theme: value });
		persistSettings();
	}

	async function persistSettings() {
		saving = true;
		saved = false;
		error = '';
		try {
			await saveUserSettings();
			saved = true;
			setTimeout(() => {
				saved = false;
			}, 2000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save settings';
		} finally {
			saving = false;
		}
	}
</script>

<div class="mx-auto flex h-full max-w-2xl flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center gap-3">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Appearance</h1>
			<p class="text-sm text-text-secondary">Customize how Firefly Desk looks</p>
		</div>
		<div class="flex-1"></div>
		{#if saving}
			<span class="flex items-center gap-1.5 text-xs text-text-secondary">
				<Loader2 size={14} class="animate-spin" /> Saving...
			</span>
		{:else if saved}
			<span class="text-xs text-success">Saved</span>
		{/if}
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Theme Selection -->
	<div
		class="rounded-lg border border-border border-t-2 border-t-ember bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Palette size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Theme</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					Choose your preferred color scheme.
				</p>
			</div>
		</div>

		<div class="flex gap-3">
			{#each themeOptions as option}
				<button
					type="button"
					class="group flex flex-1 flex-col items-center gap-2 rounded-xl border p-4 transition-all
						{$themePreference === option.value
						? 'border-ember bg-ember/5 shadow-sm'
						: 'border-border/50 hover:border-text-secondary/30'}"
					onclick={() => handleThemeChange(option.value)}
				>
					<!-- Mini preview mockup -->
					<div
						class="h-16 w-24 overflow-hidden rounded-md border border-border/50 {option.previewBg}"
					>
						<div class="h-2 {option.previewHeader}"></div>
						<div class="flex h-full">
							<div class="w-6 {option.previewSidebar}"></div>
							<div class="flex-1 space-y-1 p-1.5">
								<div class="h-1.5 w-3/4 rounded-full {option.previewText}"></div>
								<div class="h-1.5 w-1/2 rounded-full {option.previewText}"></div>
							</div>
						</div>
					</div>
					<div class="text-center">
						<span
							class="text-xs font-medium {$themePreference === option.value
								? 'text-ember'
								: 'text-text-secondary'}"
						>
							{option.label}
						</span>
						<p class="mt-0.5 text-[10px] text-text-secondary/70">
							{option.description}
						</p>
					</div>
				</button>
			{/each}
		</div>
	</div>

	<!-- Bottom spacer -->
	<div class="h-4"></div>
</div>
