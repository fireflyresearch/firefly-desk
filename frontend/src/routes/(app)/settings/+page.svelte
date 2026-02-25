<!--
  Settings profile page - User profile and preferences.

  Shows user information with avatar upload, agent behavior, notifications,
  and keyboard shortcuts.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Loader2, Bot, Bell, Keyboard, User, Camera } from 'lucide-svelte';
	import {
		userSettings,
		updateSettings,
		loadUserSettings,
		saveUserSettings
	} from '$lib/stores/settings.js';
	import { currentUser } from '$lib/stores/user.js';
	import { apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let saving = $state(false);
	let saved = $state(false);
	let error = $state('');
	let uploadingAvatar = $state(false);
	let fileInput: HTMLInputElement;

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	$effect(() => {
		loadUserSettings();
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

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

	async function handleAvatarUpload(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		// Validate on client side
		const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
		if (!allowed.includes(file.type)) {
			error = 'Please select a JPEG, PNG, GIF, or WebP image.';
			return;
		}
		if (file.size > 2 * 1024 * 1024) {
			error = 'Image must be under 2MB.';
			return;
		}

		uploadingAvatar = true;
		error = '';
		try {
			const formData = new FormData();
			formData.append('file', file);
			const resp = await apiFetch('/profile/avatar', {
				method: 'POST',
				body: formData
			});
			if (!resp.ok) {
				const body = await resp.json().catch(() => ({}));
				throw new Error(body.detail || 'Upload failed');
			}
			const data = await resp.json();
			// Update the user store with the new picture URL
			if ($currentUser) {
				$currentUser = { ...$currentUser, pictureUrl: data.picture_url };
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to upload avatar';
		} finally {
			uploadingAvatar = false;
			// Reset the input so the same file can be re-selected
			input.value = '';
		}
	}

	// -----------------------------------------------------------------------
	// Data
	// -----------------------------------------------------------------------

	let initials = $derived(
		($currentUser?.displayName ?? 'U')
			.split(' ')
			.map((part) => part[0])
			.join('')
			.toUpperCase()
			.slice(0, 2)
	);

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
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Profile</h1>
			<p class="text-sm text-text-secondary">Manage your account and preferences</p>
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

	<!-- 1. User Profile -->
	<div
		class="rounded-lg border border-border border-t-2 border-t-ember bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<User size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">User Profile</h2>
				<p class="mt-0.5 text-xs text-text-secondary">Your account information.</p>
			</div>
		</div>

		<div class="flex items-start gap-4">
			<!-- Avatar with upload overlay -->
			<div class="group relative shrink-0">
				{#if $currentUser?.pictureUrl}
					<img
						src={$currentUser.pictureUrl}
						alt={$currentUser.displayName}
						class="h-14 w-14 rounded-full object-cover"
					/>
				{:else}
					<div
						class="flex h-14 w-14 items-center justify-center rounded-full bg-accent text-lg font-medium text-white"
					>
						{initials}
					</div>
				{/if}
				<!-- Upload overlay -->
				<button
					type="button"
					onclick={() => fileInput.click()}
					disabled={uploadingAvatar}
					class="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 text-white opacity-0 transition-opacity group-hover:opacity-100 disabled:cursor-wait"
					title="Upload avatar"
				>
					{#if uploadingAvatar}
						<Loader2 size={16} class="animate-spin" />
					{:else}
						<Camera size={16} />
					{/if}
				</button>
				<input
					bind:this={fileInput}
					type="file"
					accept="image/jpeg,image/png,image/gif,image/webp"
					onchange={handleAvatarUpload}
					class="hidden"
				/>
			</div>
			<div class="flex-1 space-y-2 text-sm">
				<div class="flex justify-between">
					<span class="text-text-secondary">Name</span>
					<span class="font-medium text-text-primary"
						>{$currentUser?.displayName ?? 'Unknown'}</span
					>
				</div>
				<div class="flex justify-between">
					<span class="text-text-secondary">Email</span>
					<span class="text-text-primary">{$currentUser?.email ?? 'N/A'}</span>
				</div>
				{#if $currentUser?.department}
					<div class="flex justify-between">
						<span class="text-text-secondary">Department</span>
						<span class="text-text-primary">{$currentUser.department}</span>
					</div>
				{/if}
				{#if $currentUser?.title}
					<div class="flex justify-between">
						<span class="text-text-secondary">Title</span>
						<span class="text-text-primary">{$currentUser.title}</span>
					</div>
				{/if}
				{#if $currentUser?.roles.length}
					<div class="flex justify-between">
						<span class="text-text-secondary">Roles</span>
						<div class="flex flex-wrap gap-1">
							{#each $currentUser.roles as role}
								<span
									class="rounded-full border border-ember/30 bg-ember/10 px-2 py-0.5 text-xs font-medium text-ember"
								>
									{role}
								</span>
							{/each}
						</div>
					</div>
				{/if}
			</div>
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
				aria-label="Toggle verbose mode"
				onclick={() => handleToggle('agentVerbose')}
				class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out
					{$userSettings.agentVerbose ? 'bg-ember' : 'bg-border'}"
			>
				<span
					class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transition-transform duration-200 ease-in-out
						{$userSettings.agentVerbose ? 'translate-x-5' : 'translate-x-0'}"
				></span>
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
				aria-label="Toggle notifications"
				onclick={() => handleToggle('notificationsEnabled')}
				class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out
					{$userSettings.notificationsEnabled ? 'bg-ember' : 'bg-border'}"
			>
				<span
					class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transition-transform duration-200 ease-in-out
						{$userSettings.notificationsEnabled ? 'translate-x-5' : 'translate-x-0'}"
				></span>
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
