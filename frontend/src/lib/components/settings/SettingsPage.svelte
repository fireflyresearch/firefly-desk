<!--
  SettingsPage.svelte - Card-based settings page with user preferences.

  Sections: Appearance, Agent Behavior, Display, Keyboard Shortcuts, About.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, Loader2 } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { themePreference, setTheme, type ThemePreference } from '$lib/stores/theme.js';
	import {
		userSettings,
		updateSettings,
		loadUserSettings,
		saveUserSettings
	} from '$lib/stores/settings.js';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let saving = $state(false);
	let saved = $state(false);
	let error = $state('');

	// About section
	let appInfo = $state({
		appTitle: 'Firefly Desk',
		appVersion: '0.0.0',
		agentName: 'Ember'
	});

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	$effect(() => {
		loadUserSettings();
		fetchAppInfo();
	});

	async function fetchAppInfo() {
		try {
			const status = await apiJson<Record<string, unknown>>('/setup/status');
			appInfo = {
				appTitle: (status.app_title as string) ?? 'Firefly Desk',
				appVersion: (status.app_version as string) ?? '0.0.0',
				agentName: (status.agent_name as string) ?? 'Ember'
			};
		} catch {
			// Keep defaults
		}
	}

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleThemeChange(value: ThemePreference) {
		setTheme(value);
		updateSettings({ theme: value });
		persistSettings();
	}

	function handleToggle(key: 'agentVerbose' | 'notificationsEnabled') {
		updateSettings({ [key]: !$userSettings[key] });
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

	// -----------------------------------------------------------------------
	// Keyboard shortcuts data
	// -----------------------------------------------------------------------

	const shortcuts = [
		{ action: 'Send message', shortcut: 'Enter' },
		{ action: 'New line', shortcut: 'Shift + Enter' },
		{ action: 'Toggle dark mode', shortcut: 'TopBar button' },
		{ action: 'Toggle sidebar', shortcut: 'TopBar hamburger' }
	];
</script>

<div class="mx-auto flex h-full max-w-2xl flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div class="flex items-center gap-3">
		<button
			type="button"
			onclick={() => goto('/')}
			class="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			aria-label="Back to chat"
		>
			<ArrowLeft size={18} />
		</button>
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Settings</h1>
			<p class="text-sm text-text-secondary">Manage your preferences</p>
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

	<!-- 1. Appearance -->
	<div class="rounded-lg border border-border bg-surface p-6">
		<h2 class="mb-4 text-sm font-semibold text-text-primary">Appearance</h2>
		<p class="mb-3 text-sm text-text-secondary">Choose your preferred color scheme.</p>

		<div class="flex gap-3">
			{#each [
				{ value: 'light', label: 'Light' },
				{ value: 'dark', label: 'Dark' },
				{ value: 'system', label: 'System' }
			] as option}
				<label
					class="flex cursor-pointer items-center gap-2 rounded-md border px-4 py-2 text-sm transition-colors
						{$themePreference === option.value
						? 'border-accent bg-accent/5 font-medium text-accent'
						: 'border-border text-text-secondary hover:border-text-secondary/40'}"
				>
					<input
						type="radio"
						name="theme"
						value={option.value}
						checked={$themePreference === option.value}
						onchange={() => handleThemeChange(option.value as ThemePreference)}
						class="sr-only"
					/>
					{option.label}
				</label>
			{/each}
		</div>
	</div>

	<!-- 2. Agent Behavior -->
	<div class="rounded-lg border border-border bg-surface p-6">
		<h2 class="mb-4 text-sm font-semibold text-text-primary">Agent Behavior</h2>

		<label class="flex cursor-pointer items-center justify-between gap-4">
			<div>
				<p class="text-sm text-text-primary">Verbose mode</p>
				<p class="text-xs text-text-secondary">Show more detail in agent responses.</p>
			</div>
			<input
				type="checkbox"
				checked={$userSettings.agentVerbose}
				onchange={() => handleToggle('agentVerbose')}
				class="h-4 w-4 cursor-pointer rounded border-border accent-accent"
			/>
		</label>
	</div>

	<!-- 3. Display -->
	<div class="rounded-lg border border-border bg-surface p-6">
		<h2 class="mb-4 text-sm font-semibold text-text-primary">Notifications</h2>

		<label class="flex cursor-pointer items-center justify-between gap-4">
			<div>
				<p class="text-sm text-text-primary">Enable notifications</p>
				<p class="text-xs text-text-secondary">
					Receive notifications for agent responses and system events.
				</p>
			</div>
			<input
				type="checkbox"
				checked={$userSettings.notificationsEnabled}
				onchange={() => handleToggle('notificationsEnabled')}
				class="h-4 w-4 cursor-pointer rounded border-border accent-accent"
			/>
		</label>
	</div>

	<!-- 4. Keyboard Shortcuts -->
	<div class="rounded-lg border border-border bg-surface p-6">
		<h2 class="mb-4 text-sm font-semibold text-text-primary">Keyboard Shortcuts</h2>

		<div class="overflow-hidden rounded-md border border-border">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-border bg-surface-secondary">
						<th class="px-4 py-2 text-left text-xs font-medium text-text-secondary">
							Action
						</th>
						<th class="px-4 py-2 text-left text-xs font-medium text-text-secondary">
							Shortcut
						</th>
					</tr>
				</thead>
				<tbody>
					{#each shortcuts as row, i}
						<tr class="border-b border-border last:border-b-0 {i % 2 === 1 ? 'bg-surface-secondary/50' : ''}">
							<td class="px-4 py-2 text-text-primary">{row.action}</td>
							<td class="px-4 py-2">
								<kbd
									class="rounded border border-border bg-surface-secondary px-2 py-0.5 font-mono text-xs text-text-secondary"
								>
									{row.shortcut}
								</kbd>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>

	<!-- 5. About -->
	<div class="rounded-lg border border-border bg-surface p-6">
		<h2 class="mb-4 text-sm font-semibold text-text-primary">About</h2>

		<div class="space-y-2 text-sm">
			<div class="flex justify-between">
				<span class="text-text-secondary">Application</span>
				<span class="font-medium text-text-primary">{appInfo.appTitle}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-text-secondary">Version</span>
				<span class="font-mono text-text-primary">{appInfo.appVersion}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-text-secondary">Agent</span>
				<span class="font-medium text-text-primary">{appInfo.agentName}</span>
			</div>
		</div>
	</div>

	<!-- Bottom spacer -->
	<div class="h-4"></div>
</div>
