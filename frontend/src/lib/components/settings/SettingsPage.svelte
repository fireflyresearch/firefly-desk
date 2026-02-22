<!--
  SettingsPage.svelte - Card-based settings page with user preferences.

  Sections: Appearance, Agent Behavior, Notifications, Keyboard Shortcuts, About.
  Warm industrial design — ember accents, surface-elevated cards, micro-interactions.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, Loader2, Palette, Bot, Bell, Keyboard, Info } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { themePreference, setTheme, type ThemePreference } from '$lib/stores/theme.js';
	import {
		userSettings,
		updateSettings,
		loadUserSettings,
		saveUserSettings
	} from '$lib/stores/settings.js';
	import { apiJson } from '$lib/services/api.js';
	import EmberAvatar from '$lib/components/chat/EmberAvatar.svelte';

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
	// Theme preview definitions
	// -----------------------------------------------------------------------

	const themeOptions: {
		value: ThemePreference;
		label: string;
		previewBg: string;
		previewHeader: string;
		previewSidebar: string;
		previewText: string;
	}[] = [
		{
			value: 'light',
			label: 'Light',
			previewBg: 'bg-white',
			previewHeader: 'bg-gray-200',
			previewSidebar: 'bg-gray-100',
			previewText: 'bg-gray-300'
		},
		{
			value: 'dark',
			label: 'Dark',
			previewBg: 'bg-gray-900',
			previewHeader: 'bg-gray-800',
			previewSidebar: 'bg-gray-800',
			previewText: 'bg-gray-600'
		},
		{
			value: 'system',
			label: 'System',
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
				<h2 class="text-sm font-semibold text-text-primary">Appearance</h2>
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
					<span
						class="text-xs font-medium {$themePreference === option.value
							? 'text-ember'
							: 'text-text-secondary'}"
					>
						{option.label}
					</span>
				</button>
			{/each}
		</div>
	</div>

	<!-- 2. Agent Behavior -->
	<div
		class="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Bot size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Agent Behavior</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					Configure how Ember responds to your requests.
				</p>
			</div>
		</div>

		<div class="flex items-center justify-between gap-4">
			<div>
				<p class="text-sm text-text-primary">Verbose mode</p>
				<p class="text-xs text-text-secondary">Show more detail in agent responses.</p>
			</div>
			<button
				type="button"
				role="switch"
				aria-checked={$userSettings.agentVerbose}
				onclick={() => handleToggle('agentVerbose')}
				class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out
					{$userSettings.agentVerbose ? 'bg-ember' : 'bg-border'}"
			>
				<span
					class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transition-transform duration-200 ease-in-out
						{$userSettings.agentVerbose ? 'translate-x-5' : 'translate-x-0'}"
				/>
			</button>
		</div>
	</div>

	<!-- 3. Notifications -->
	<div
		class="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Bell size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Notifications</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					Control alerts for agent activity and system events.
				</p>
			</div>
		</div>

		<div class="flex items-center justify-between gap-4">
			<div>
				<p class="text-sm text-text-primary">Enable notifications</p>
				<p class="text-xs text-text-secondary">
					Receive notifications for agent responses and system events.
				</p>
			</div>
			<button
				type="button"
				role="switch"
				aria-checked={$userSettings.notificationsEnabled}
				onclick={() => handleToggle('notificationsEnabled')}
				class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out
					{$userSettings.notificationsEnabled ? 'bg-ember' : 'bg-border'}"
			>
				<span
					class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transition-transform duration-200 ease-in-out
						{$userSettings.notificationsEnabled ? 'translate-x-5' : 'translate-x-0'}"
				/>
			</button>
		</div>
	</div>

	<!-- 4. Keyboard Shortcuts -->
	<div
		class="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Keyboard size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Keyboard Shortcuts</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					Quick actions to speed up your workflow.
				</p>
			</div>
		</div>

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
						<tr
							class="border-b border-border last:border-b-0 {i % 2 === 1
								? 'bg-surface-secondary/50'
								: ''}"
						>
							<td class="px-4 py-2.5 text-text-primary">{row.action}</td>
							<td class="px-4 py-2.5">
								{#each row.shortcut.split(' + ') as part, j}
									{#if j > 0}
										<span class="mx-1 text-xs text-text-secondary">+</span>
									{/if}
									<kbd>{part}</kbd>
								{/each}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>

	<!-- 5. About -->
	<div
		class="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Info size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">About</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					Application information and licensing.
				</p>
			</div>
		</div>

		<div class="flex items-start gap-4">
			<EmberAvatar size={32} />
			<div class="flex-1 space-y-2 text-sm">
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
				<div class="pt-2 text-xs text-text-secondary">
					Apache License 2.0 &mdash; Firefly Software Solutions Inc.
				</div>
			</div>
		</div>
	</div>

	<!-- Bottom spacer -->
	<div class="h-4"></div>
</div>

<style>
	kbd {
		background: linear-gradient(
			180deg,
			var(--color-surface-elevated),
			var(--color-surface-secondary)
		);
		border: 1px solid var(--color-border);
		border-bottom-width: 2px;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
		border-radius: 6px;
		padding: 2px 8px;
		font-size: 12px;
		font-family:
			ui-monospace,
			SFMono-Regular,
			Menlo,
			Monaco,
			Consolas,
			monospace;
		color: var(--color-text-secondary);
	}
</style>
