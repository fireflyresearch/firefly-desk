<!--
  SSOManager.svelte - CRUD interface for OIDC provider configuration.

  Lists SSO providers in a table with inline forms for adding / editing.
  Supports testing OIDC discovery connectivity and toggling active state.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Pencil,
		Trash2,
		X,
		Save,
		Loader2,
		Zap,
		CheckCircle,
		XCircle,
		ToggleLeft,
		ToggleRight
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		embedded?: boolean;
	}

	let { embedded = false }: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface OIDCProvider {
		id: string;
		provider_type: string;
		display_name: string;
		issuer_url: string;
		client_id: string;
		has_client_secret: boolean;
		tenant_id: string | null;
		scopes: string[] | null;
		roles_claim: string | null;
		permissions_claim: string | null;
		allowed_email_domains: string[] | null;
		is_active: boolean;
		created_at: string | null;
		updated_at: string | null;
	}

	interface TestResult {
		reachable: boolean;
		issuer: string | null;
		authorization_endpoint: string | null;
		token_endpoint: string | null;
		error: string | null;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const PROVIDER_TYPES = [
		{ value: 'keycloak', label: 'Keycloak' },
		{ value: 'google', label: 'Google' },
		{ value: 'microsoft', label: 'Microsoft' },
		{ value: 'auth0', label: 'Auth0' },
		{ value: 'cognito', label: 'AWS Cognito' },
		{ value: 'okta', label: 'Okta' }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providers = $state<OIDCProvider[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let formData = $state({
		provider_type: 'keycloak',
		display_name: '',
		issuer_url: '',
		client_id: '',
		client_secret: '',
		tenant_id: '',
		scopes: '',
		roles_claim: '',
		permissions_claim: '',
		allowed_email_domains: ''
	});
	let saving = $state(false);

	// Test connection state
	let testingId = $state<string | null>(null);
	let testResults = $state<Record<string, TestResult>>({});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadProviders() {
		loading = true;
		error = '';
		try {
			providers = await apiJson<OIDCProvider[]>('/admin/oidc-providers');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load providers';
		} finally {
			loading = false;
		}
	}

	// Initial load
	$effect(() => {
		loadProviders();
	});

	// -----------------------------------------------------------------------
	// Form actions
	// -----------------------------------------------------------------------

	function openAddForm() {
		editingId = null;
		formData = {
			provider_type: 'keycloak',
			display_name: '',
			issuer_url: '',
			client_id: '',
			client_secret: '',
			tenant_id: '',
			scopes: '',
			roles_claim: '',
			permissions_claim: '',
			allowed_email_domains: ''
		};
		showForm = true;
	}

	function openEditForm(provider: OIDCProvider) {
		editingId = provider.id;
		formData = {
			provider_type: provider.provider_type,
			display_name: provider.display_name,
			issuer_url: provider.issuer_url,
			client_id: provider.client_id,
			client_secret: '',
			tenant_id: provider.tenant_id || '',
			scopes: provider.scopes?.join(', ') || '',
			roles_claim: provider.roles_claim || '',
			permissions_claim: provider.permissions_claim || '',
			allowed_email_domains: provider.allowed_email_domains?.join(', ') || ''
		};
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editingId = null;
	}

	async function submitForm() {
		saving = true;
		error = '';

		const scopesList = formData.scopes
			? formData.scopes
					.split(',')
					.map((s) => s.trim())
					.filter(Boolean)
			: null;

		const domainsList = formData.allowed_email_domains
			? formData.allowed_email_domains
					.split(',')
					.map((d) => d.trim())
					.filter(Boolean)
			: null;

		const payload: Record<string, unknown> = {
			provider_type: formData.provider_type,
			display_name: formData.display_name,
			issuer_url: formData.issuer_url,
			client_id: formData.client_id,
			tenant_id: formData.tenant_id || null,
			scopes: scopesList,
			roles_claim: formData.roles_claim || null,
			permissions_claim: formData.permissions_claim || null,
			allowed_email_domains: domainsList,
			is_active: true
		};

		// Only send client_secret if user provided one
		if (formData.client_secret) {
			payload.client_secret = formData.client_secret;
		}

		try {
			if (editingId) {
				await apiJson(`/admin/oidc-providers/${editingId}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/admin/oidc-providers', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			showForm = false;
			editingId = null;
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save provider';
		} finally {
			saving = false;
		}
	}

	async function deleteProvider(id: string) {
		error = '';
		try {
			await apiFetch(`/admin/oidc-providers/${id}`, { method: 'DELETE' });
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete provider';
		}
	}

	async function toggleActive(provider: OIDCProvider) {
		error = '';
		try {
			await apiJson(`/admin/oidc-providers/${provider.id}`, {
				method: 'PUT',
				body: JSON.stringify({
					provider_type: provider.provider_type,
					display_name: provider.display_name,
					issuer_url: provider.issuer_url,
					client_id: provider.client_id,
					tenant_id: provider.tenant_id,
					scopes: provider.scopes,
					roles_claim: provider.roles_claim,
					permissions_claim: provider.permissions_claim,
					allowed_email_domains: provider.allowed_email_domains,
					is_active: !provider.is_active
				})
			});
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to toggle provider';
		}
	}

	async function testConnection(provider: OIDCProvider) {
		testingId = provider.id;
		try {
			const result = await apiJson<TestResult>(
				`/admin/oidc-providers/${provider.id}/test`,
				{ method: 'POST' }
			);
			testResults = { ...testResults, [provider.id]: result };
		} catch (e) {
			testResults = {
				...testResults,
				[provider.id]: {
					reachable: false,
					issuer: null,
					authorization_endpoint: null,
					token_endpoint: null,
					error: e instanceof Error ? e.message : 'Test failed'
				}
			};
		} finally {
			testingId = null;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function providerLabel(type: string): string {
		return PROVIDER_TYPES.find((t) => t.value === type)?.label ?? type;
	}

	let showsTenantId = $derived(formData.provider_type === 'microsoft');
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Single Sign-On</h1>
				<p class="text-sm text-text-secondary">
					Manage OIDC identity providers for SSO authentication
				</p>
			</div>
			<button
				type="button"
				onclick={openAddForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Add Provider
			</button>
		</div>
	{:else}
		<div class="flex justify-end">
			<button
				type="button"
				onclick={openAddForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Add Provider
			</button>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Inline form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">
					{editingId ? 'Edit Provider' : 'New OIDC Provider'}
				</h3>
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
					<span class="text-xs font-medium text-text-secondary">Provider Type</span>
					<select
						bind:value={formData.provider_type}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						{#each PROVIDER_TYPES as pt}
							<option value={pt.value}>{pt.label}</option>
						{/each}
					</select>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Display Name</span>
					<input
						type="text"
						bind:value={formData.display_name}
						required
						placeholder="e.g. Corporate SSO"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Issuer URL</span>
					<input
						type="url"
						bind:value={formData.issuer_url}
						required
						placeholder="https://auth.example.com/realms/myorg"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Client ID</span>
					<input
						type="text"
						bind:value={formData.client_id}
						required
						placeholder="firefly-desk"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						Client Secret
						{#if editingId}
							<span class="text-text-secondary/60">(leave blank to keep existing)</span>
						{/if}
					</span>
					<input
						type="password"
						bind:value={formData.client_secret}
						placeholder={editingId ? '********' : 'Enter client secret'}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				{#if showsTenantId}
					<label class="col-span-2 flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">
							Tenant ID
							<span class="text-text-secondary/60">(Microsoft only)</span>
						</span>
						<input
							type="text"
							bind:value={formData.tenant_id}
							placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				{/if}

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						Scopes
						<span class="text-text-secondary/60">(comma-separated)</span>
					</span>
					<input
						type="text"
						bind:value={formData.scopes}
						placeholder="openid, profile, email"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						Roles Claim
						<span class="text-text-secondary/60">(optional)</span>
					</span>
					<input
						type="text"
						bind:value={formData.roles_claim}
						placeholder="realm_access.roles"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						Allowed Email Domains
						<span class="text-text-secondary/60">(optional, comma-separated)</span>
					</span>
					<input
						type="text"
						bind:value={formData.allowed_email_domains}
						placeholder="example.com, mycompany.org"
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
						{editingId ? 'Update' : 'Create'}
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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Issuer URL
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Client ID
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Active
							</th>
							<th class="w-48 px-4 py-2 text-xs font-medium text-text-secondary">
								Actions
							</th>
						</tr>
					</thead>
					<tbody>
						{#each providers as provider, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2">
									<div class="font-medium text-text-primary">
										{provider.display_name}
									</div>
									{#if provider.allowed_email_domains && provider.allowed_email_domains.length > 0}
										<div class="mt-0.5 text-xs text-text-secondary">
											{provider.allowed_email_domains.join(', ')}
										</div>
									{/if}
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										{providerLabel(provider.provider_type)}
									</span>
								</td>
								<td class="max-w-[240px] truncate px-4 py-2 font-mono text-xs text-text-secondary">
									{provider.issuer_url}
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{provider.client_id}
								</td>
								<td class="px-4 py-2">
									{#if provider.is_active}
										<span
											class="inline-block rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
										>
											Active
										</span>
									{:else}
										<span
											class="inline-block rounded-full bg-text-secondary/10 px-2 py-0.5 text-xs font-medium text-text-secondary"
										>
											Inactive
										</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={() => openEditForm(provider)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Edit"
										>
											<Pencil size={14} />
										</button>
										<button
											type="button"
											onclick={() => testConnection(provider)}
											disabled={testingId === provider.id}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent disabled:opacity-50"
											title="Test Connection"
										>
											{#if testingId === provider.id}
												<Loader2 size={14} class="animate-spin" />
											{:else}
												<Zap size={14} />
											{/if}
										</button>
										<button
											type="button"
											onclick={() => toggleActive(provider)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title={provider.is_active ? 'Deactivate' : 'Activate'}
										>
											{#if provider.is_active}
												<ToggleRight size={14} class="text-success" />
											{:else}
												<ToggleLeft size={14} />
											{/if}
										</button>
										<button
											type="button"
											onclick={() => deleteProvider(provider.id)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
											title="Delete"
										>
											<Trash2 size={14} />
										</button>
									</div>

									<!-- Inline test result -->
									{#if testResults[provider.id]}
										{@const result = testResults[provider.id]}
										<div class="mt-1 text-xs">
											{#if result.reachable}
												<span
													class="inline-flex items-center gap-1 text-success"
												>
													<CheckCircle size={12} />
													Discovery OK
													{#if result.issuer}
														<span class="text-text-secondary">
															({result.issuer})
														</span>
													{/if}
												</span>
											{:else}
												<span
													class="inline-flex items-center gap-1 text-danger"
												>
													<XCircle size={12} />
													{result.error || 'Unreachable'}
												</span>
											{/if}
										</div>
									{/if}
								</td>
							</tr>
						{:else}
							<tr>
								<td
									colspan="6"
									class="px-4 py-8 text-center text-sm text-text-secondary"
								>
									No OIDC providers configured. Add one to enable single sign-on.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
