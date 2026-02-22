<!--
  CredentialVault.svelte - Credential management interface.

  Lists credentials in a table with rotate and revoke actions.
  Never displays encrypted values.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		RefreshCw,
		Trash2,
		X,
		Save,
		Loader2,
		ShieldCheck
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Credential {
		id: string;
		name: string;
		system: string;
		type: string;
		expires_at: string | null;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let credentials = $state<Credential[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let formData = $state({ name: '', system: '', type: 'api_key', secret: '', expires_at: '' });
	let saving = $state(false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadCredentials() {
		loading = true;
		error = '';
		try {
			credentials = await apiJson<Credential[]>('/credentials');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load credentials';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadCredentials();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function openAddForm() {
		formData = { name: '', system: '', type: 'api_key', secret: '', expires_at: '' };
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
	}

	async function submitForm() {
		saving = true;
		error = '';
		const payload: Record<string, string> = {
			name: formData.name,
			system: formData.system,
			type: formData.type,
			secret: formData.secret
		};
		if (formData.expires_at) {
			payload.expires_at = formData.expires_at;
		}

		try {
			await apiJson('/credentials', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			showForm = false;
			await loadCredentials();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create credential';
		} finally {
			saving = false;
		}
	}

	async function rotateCredential(id: string) {
		error = '';
		const newSecret = prompt('Enter new secret value:');
		if (!newSecret) return;

		try {
			await apiJson(`/credentials/${id}`, {
				method: 'PUT',
				body: JSON.stringify({ secret: newSecret })
			});
			await loadCredentials();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to rotate credential';
		}
	}

	async function revokeCredential(id: string) {
		error = '';
		try {
			await apiJson(`/credentials/${id}`, { method: 'DELETE' });
			await loadCredentials();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to revoke credential';
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function formatExpiry(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	function isExpired(dateStr: string | null): boolean {
		if (!dateStr) return false;
		return new Date(dateStr) < new Date();
	}

	function typeLabel(type: string): string {
		switch (type) {
			case 'api_key':
				return 'API Key';
			case 'oauth2':
				return 'OAuth 2.0';
			case 'basic':
				return 'Basic Auth';
			case 'bearer':
				return 'Bearer Token';
			default:
				return type;
		}
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Credential Vault</h1>
			<p class="text-sm text-text-secondary">Manage authentication credentials for external systems</p>
		</div>
		<button
			type="button"
			onclick={openAddForm}
			class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			<Plus size={16} />
			Add Credential
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Inline form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">New Credential</h3>
				<button
					type="button"
					onclick={cancelForm}
					class="text-text-secondary hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<form
				onsubmit={(e) => {
					e.preventDefault();
					submitForm();
				}}
				class="grid grid-cols-2 gap-3"
			>
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Name</span>
					<input
						type="text"
						bind:value={formData.name}
						required
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">System</span>
					<input
						type="text"
						bind:value={formData.system}
						required
						placeholder="e.g. salesforce"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Type</span>
					<select
						bind:value={formData.type}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						<option value="api_key">API Key</option>
						<option value="oauth2">OAuth 2.0</option>
						<option value="basic">Basic Auth</option>
						<option value="bearer">Bearer Token</option>
					</select>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Expires At (optional)</span>
					<input
						type="date"
						bind:value={formData.expires_at}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Secret Value</span>
					<input
						type="password"
						bind:value={formData.secret}
						required
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<div class="col-span-2 flex justify-end gap-2 pt-1">
					<button
						type="button"
						onclick={cancelForm}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="submit"
						disabled={saving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						Create
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="rounded-lg border border-border bg-surface">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Name</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">System</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Expires</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Value</th>
							<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each credentials as cred, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2 font-medium text-text-primary">{cred.name}</td>
								<td class="px-4 py-2 text-text-secondary">{cred.system}</td>
								<td class="px-4 py-2">
									<span class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary">
										{typeLabel(cred.type)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="text-xs {isExpired(cred.expires_at)
											? 'font-medium text-danger'
											: 'text-text-secondary'}"
									>
										{formatExpiry(cred.expires_at)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span class="inline-flex items-center gap-1 text-xs text-text-secondary">
										<ShieldCheck size={12} />
										Encrypted
									</span>
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={() => rotateCredential(cred.id)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Rotate"
										>
											<RefreshCw size={14} />
										</button>
										<button
											type="button"
											onclick={() => revokeCredential(cred.id)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
											title="Revoke"
										>
											<Trash2 size={14} />
										</button>
									</div>
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="6" class="px-4 py-8 text-center text-sm text-text-secondary">
									No credentials stored. Add one to get started.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
