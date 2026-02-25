<!--
  GitProviderManager.svelte - CRUD interface for Git provider OAuth configuration.

  Lists Git providers in a table with inline forms for adding / editing.
  Supports testing connectivity and toggling active state.

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
		ToggleRight,
		GitBranch,
		Lock
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

	interface GitProvider {
		id: string;
		provider_type: string;
		display_name: string;
		base_url: string;
		auth_method: string;
		client_id: string | null;
		has_client_secret: boolean;
		oauth_authorize_url: string | null;
		oauth_token_url: string | null;
		scopes: string[] | null;
		is_active: boolean;
		created_at: string | null;
		updated_at: string | null;
	}

	interface TestResult {
		valid: boolean;
		error: string | null;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const PROVIDER_TYPES = [
		{ value: 'github', label: 'GitHub' },
		{ value: 'gitlab', label: 'GitLab' },
		{ value: 'bitbucket', label: 'Bitbucket' }
	];

	const PROVIDER_DEFAULTS: Record<
		string,
		{ base_url: string; oauth_authorize_url: string; oauth_token_url: string; scopes: string }
	> = {
		github: {
			base_url: 'https://api.github.com',
			oauth_authorize_url: 'https://github.com/login/oauth/authorize',
			oauth_token_url: 'https://github.com/login/oauth/access_token',
			scopes: 'repo'
		},
		gitlab: {
			base_url: 'https://gitlab.com',
			oauth_authorize_url: 'https://gitlab.com/oauth/authorize',
			oauth_token_url: 'https://gitlab.com/oauth/token',
			scopes: 'read_api, read_repository'
		},
		bitbucket: {
			base_url: 'https://api.bitbucket.org/2.0',
			oauth_authorize_url: 'https://bitbucket.org/site/oauth2/authorize',
			oauth_token_url: 'https://bitbucket.org/site/oauth2/access_token',
			scopes: 'repository'
		}
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providers = $state<GitProvider[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let formData = $state({
		provider_type: 'github',
		display_name: '',
		base_url: 'https://api.github.com',
		auth_method: 'pat' as 'oauth' | 'pat',
		client_id: '',
		client_secret: '',
		oauth_authorize_url: 'https://github.com/login/oauth/authorize',
		oauth_token_url: 'https://github.com/login/oauth/access_token',
		scopes: 'repo'
	});
	let saving = $state(false);

	// Test connection state
	let testingId = $state<string | null>(null);
	let testResults = $state<Record<string, TestResult>>({});

	// -----------------------------------------------------------------------
	// Auto-fill defaults when provider type changes (only for new providers)
	// -----------------------------------------------------------------------

	$effect(() => {
		if (!editingId && formData.provider_type in PROVIDER_DEFAULTS) {
			const defaults = PROVIDER_DEFAULTS[formData.provider_type];
			formData.base_url = defaults.base_url;
			formData.oauth_authorize_url = defaults.oauth_authorize_url;
			formData.oauth_token_url = defaults.oauth_token_url;
			formData.scopes = defaults.scopes;
		}
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadProviders() {
		loading = true;
		error = '';
		try {
			providers = await apiJson<GitProvider[]>('/admin/git-providers');
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
			provider_type: 'github',
			display_name: '',
			base_url: 'https://api.github.com',
			auth_method: 'pat',
			client_id: '',
			client_secret: '',
			oauth_authorize_url: 'https://github.com/login/oauth/authorize',
			oauth_token_url: 'https://github.com/login/oauth/access_token',
			scopes: 'repo'
		};
		showForm = true;
	}

	function openEditForm(provider: GitProvider) {
		editingId = provider.id;
		formData = {
			provider_type: provider.provider_type,
			display_name: provider.display_name,
			base_url: provider.base_url,
			auth_method: (provider.auth_method || 'oauth') as 'oauth' | 'pat',
			client_id: provider.client_id || '',
			client_secret: '',
			oauth_authorize_url: provider.oauth_authorize_url || '',
			oauth_token_url: provider.oauth_token_url || '',
			scopes: provider.scopes?.join(', ') || ''
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

		const isPat = formData.auth_method === 'pat';

		const scopesList =
			!isPat && formData.scopes
				? formData.scopes
						.split(',')
						.map((s) => s.trim())
						.filter(Boolean)
				: null;

		const payload: Record<string, unknown> = {
			provider_type: formData.provider_type,
			display_name: formData.display_name,
			base_url: formData.base_url,
			auth_method: formData.auth_method,
			client_id: isPat ? null : formData.client_id || null,
			oauth_authorize_url: isPat ? null : formData.oauth_authorize_url || null,
			oauth_token_url: isPat ? null : formData.oauth_token_url || null,
			scopes: scopesList,
			is_active: true
		};

		// For PAT: client_secret holds the PAT token
		// For OAuth: client_secret holds the OAuth client secret
		if (formData.client_secret) {
			payload.client_secret = formData.client_secret;
		}

		try {
			if (editingId) {
				await apiJson(`/admin/git-providers/${editingId}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/admin/git-providers', {
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
			await apiFetch(`/admin/git-providers/${id}`, { method: 'DELETE' });
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete provider';
		}
	}

	async function toggleActive(provider: GitProvider) {
		error = '';
		try {
			await apiJson(`/admin/git-providers/${provider.id}`, {
				method: 'PUT',
				body: JSON.stringify({
					provider_type: provider.provider_type,
					display_name: provider.display_name,
					base_url: provider.base_url,
					auth_method: provider.auth_method || 'oauth',
					client_id: provider.client_id,
					oauth_authorize_url: provider.oauth_authorize_url,
					oauth_token_url: provider.oauth_token_url,
					scopes: provider.scopes,
					is_active: !provider.is_active
				})
			});
			await loadProviders();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to toggle provider';
		}
	}

	async function testConnection(provider: GitProvider) {
		testingId = provider.id;
		try {
			const result = await apiJson<TestResult>(
				`/admin/git-providers/${provider.id}/test`,
				{ method: 'POST' }
			);
			testResults = { ...testResults, [provider.id]: result };
		} catch (e) {
			testResults = {
				...testResults,
				[provider.id]: {
					valid: false,
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
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Git Providers</h1>
				<p class="text-sm text-text-secondary">
					Manage Git provider connections for repository browsing and import
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
					{editingId ? 'Edit Provider' : 'New Git Provider'}
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
						placeholder="e.g. GitHub Enterprise"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Base URL</span>
					<input
						type="url"
						bind:value={formData.base_url}
						required
						placeholder="https://api.github.com"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<!-- Auth Method Toggle -->
				<div class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Authentication Method</span>
					<div class="flex gap-2">
						<button
							type="button"
							onclick={() => (formData.auth_method = 'pat')}
							class="flex-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors {formData.auth_method === 'pat'
								? 'border-accent bg-accent/10 text-accent'
								: 'border-border text-text-secondary hover:bg-surface-hover'}"
						>
							<Lock size={14} class="mb-0.5 mr-1 inline-block" />
							Personal Access Token
						</button>
						<button
							type="button"
							onclick={() => (formData.auth_method = 'oauth')}
							class="flex-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors {formData.auth_method === 'oauth'
								? 'border-accent bg-accent/10 text-accent'
								: 'border-border text-text-secondary hover:bg-surface-hover'}"
						>
							<GitBranch size={14} class="mb-0.5 mr-1 inline-block" />
							OAuth App
						</button>
					</div>
				</div>

				{#if formData.auth_method === 'pat'}
					<!-- PAT fields -->
					<label class="col-span-2 flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">
							Personal Access Token
							{#if editingId}
								<span class="text-text-secondary/60">(leave blank to keep existing)</span>
							{/if}
						</span>
						<input
							type="password"
							bind:value={formData.client_secret}
							placeholder={editingId ? '********' : 'ghp_xxxx / glpat-xxxx'}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
						<span class="text-xs text-text-secondary/60">
							Stored encrypted. Used for all Git operations with this provider.
						</span>
					</label>
				{:else}
					<!-- OAuth fields -->
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Client ID</span>
						<input
							type="text"
							bind:value={formData.client_id}
							required
							placeholder="OAuth app client ID"
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

					<label class="col-span-2 flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">OAuth Authorize URL</span>
						<input
							type="url"
							bind:value={formData.oauth_authorize_url}
							placeholder="https://github.com/login/oauth/authorize"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="col-span-2 flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">OAuth Token URL</span>
						<input
							type="url"
							bind:value={formData.oauth_token_url}
							placeholder="https://github.com/login/oauth/access_token"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">
							Scopes
							<span class="text-text-secondary/60">(comma-separated)</span>
						</span>
						<input
							type="text"
							bind:value={formData.scopes}
							placeholder="repo"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				{/if}

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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Auth
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Base URL
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Secret / Token
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
									<span
										class="mt-0.5 inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										{providerLabel(provider.provider_type)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {provider.auth_method === 'pat'
											? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
											: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'}"
									>
										{provider.auth_method === 'pat' ? 'PAT' : 'OAuth'}
									</span>
								</td>
								<td class="max-w-[240px] truncate px-4 py-2 font-mono text-xs text-text-secondary">
									{provider.base_url}
								</td>
								<td class="px-4 py-2">
									{#if provider.has_client_secret}
										<span
											class="inline-block rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
										>
											Configured
										</span>
									{:else}
										<span
											class="inline-block rounded-full bg-text-secondary/10 px-2 py-0.5 text-xs font-medium text-text-secondary"
										>
											Not set
										</span>
									{/if}
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
											{#if result.valid}
												<span
													class="inline-flex items-center gap-1 text-success"
												>
													<CheckCircle size={12} />
													Connection OK
												</span>
											{:else}
												<span
													class="inline-flex items-center gap-1 text-danger"
												>
													<XCircle size={12} />
													{result.error || 'Connection failed'}
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
									No Git providers configured. Add one to enable repository browsing and import.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
