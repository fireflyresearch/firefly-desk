<!--
  CredentialVault.svelte - Credential management interface.

  Lists credentials in a table with rotate and revoke actions.
  Never displays encrypted values. Links credentials to catalog systems.

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
		ShieldCheck,
		Shield,
		ChevronDown
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Credential {
		id: string;
		name: string;
		system_id: string;
		credential_type: string;
		expires_at: string | null;
		last_rotated: string | null;
	}

	interface CatalogSystem {
		id: string;
		name: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let credentials = $state<Credential[]>([]);
	let systems = $state<CatalogSystem[]>([]);
	let loading = $state(true);
	let error = $state('');

	// KMS status
	let kmsStatus = $state<{ provider: string; is_dev_key: boolean } | null>(null);
	let showEncryption = $state(false);

	// Form state
	let showForm = $state(false);
	let formData = $state({
		name: '',
		system_id: '',
		credential_type: 'api_key',
		encrypted_value: '',
		expires_at: ''
	});
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

	async function loadSystems() {
		try {
			const result = await apiJson<{ items: CatalogSystem[]; total: number }>('/catalog/systems');
			systems = result.items;
		} catch {
			// Non-fatal: form will fall back to text input
		}
	}

	async function loadKmsStatus() {
		try {
			kmsStatus = await apiJson<{ provider: string; is_dev_key: boolean }>(
				'/credentials/kms-status'
			);
		} catch {
			/* ignore -- non-critical */
		}
	}

	$effect(() => {
		loadCredentials();
		loadSystems();
		loadKmsStatus();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	function openAddForm() {
		formData = {
			name: '',
			system_id: '',
			credential_type: 'api_key',
			encrypted_value: '',
			expires_at: ''
		};
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
	}

	async function submitForm() {
		saving = true;
		error = '';
		const payload: Record<string, string | null> = {
			name: formData.name,
			system_id: formData.system_id,
			credential_type: formData.credential_type,
			encrypted_value: formData.encrypted_value,
			expires_at: formData.expires_at || null
		};

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
				body: JSON.stringify({ encrypted_value: newSecret })
			});
			await loadCredentials();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to rotate credential';
		}
	}

	async function revokeCredential(id: string) {
		error = '';
		if (!confirm('Are you sure you want to revoke this credential? This cannot be undone.')) return;

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

	function systemName(systemId: string): string {
		const system = systems.find((s) => s.id === systemId);
		return system?.name ?? systemId;
	}

	function formatExpiry(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	function formatRotated(dateStr: string | null): string {
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
			case 'mutual_tls':
				return 'Mutual TLS';
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
			<p class="text-sm text-text-secondary">
				Manage authentication credentials for external systems
			</p>
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
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Encryption Settings (collapsible) -->
	<div class="rounded-lg border border-border bg-surface">
		<button
			type="button"
			onclick={() => (showEncryption = !showEncryption)}
			class="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover"
		>
			<div class="flex items-center gap-2">
				<Shield size={16} class="text-accent" />
				<span>Encryption Settings</span>
			</div>
			<ChevronDown
				size={16}
				class="text-text-secondary transition-transform {showEncryption ? 'rotate-180' : ''}"
			/>
		</button>
		{#if showEncryption && kmsStatus}
			<div class="border-t border-border px-4 py-4">
				{#if kmsStatus.is_dev_key}
					<div
						class="mb-3 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-warning"
					>
						Using development encryption key. Set FLYDESK_CREDENTIAL_ENCRYPTION_KEY for
						production.
					</div>
				{/if}
				<div class="flex items-center gap-3 text-sm">
					<span class="text-text-secondary">Provider:</span>
					<span class="font-medium capitalize">{kmsStatus.provider}</span>
				</div>
				<p class="mt-2 text-xs text-text-secondary">
					Provider configuration requires environment variable changes and application
					restart.
				</p>
			</div>
		{/if}
	</div>

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
						placeholder="e.g. Production API Key"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">System</span>
					{#if systems.length > 0}
						<select
							bind:value={formData.system_id}
							required
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						>
							<option value="" disabled>Select a system...</option>
							{#each systems as system}
								<option value={system.id}>{system.name}</option>
							{/each}
						</select>
					{:else}
						<input
							type="text"
							bind:value={formData.system_id}
							required
							placeholder="System ID"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					{/if}
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Type</span>
					<select
						bind:value={formData.credential_type}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						<option value="api_key">API Key</option>
						<option value="oauth2">OAuth 2.0</option>
						<option value="basic">Basic Auth</option>
						<option value="bearer">Bearer Token</option>
						<option value="mutual_tls">Mutual TLS</option>
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
						bind:value={formData.encrypted_value}
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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Last Rotated</th>
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
								<td class="px-4 py-2 text-text-secondary">{systemName(cred.system_id)}</td>
								<td class="px-4 py-2">
									<span
										class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
									>
										{typeLabel(cred.credential_type)}
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
								<td class="px-4 py-2 text-xs text-text-secondary">
									{formatRotated(cred.last_rotated)}
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
								<td colspan="7" class="px-4 py-8 text-center text-sm text-text-secondary">
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
