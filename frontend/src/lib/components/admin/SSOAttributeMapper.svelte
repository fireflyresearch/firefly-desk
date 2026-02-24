<!--
  SSOAttributeMapper.svelte - CRUD interface for SSO claim-to-header mappings.

  Lists SSO attribute mappings in a table with an inline form for
  creating and editing mappings. Supports delete with confirmation.
  Used to forward SSO claims as HTTP headers when the agent calls
  backoffice APIs on behalf of a user.

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
		ArrowLeftRight
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

	interface SSOAttributeMapping {
		id: string;
		claim_path: string;
		target_header: string;
		target_type: 'header' | 'query_param';
		system_filter: string | null;
		transform: string | null;
	}

	interface CatalogSystem {
		id: string;
		name: string;
		status: string;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const TRANSFORMS = [
		{ value: '', label: 'None (pass-through)' },
		{ value: 'uppercase', label: 'Uppercase' },
		{ value: 'lowercase', label: 'Lowercase' },
		{ value: 'base64', label: 'Base64 Encode' },
		{ value: 'prefix:', label: 'Prefix (custom)' }
	];

	const TARGET_TYPES = [
		{ value: 'header', label: 'HTTP Header' },
		{ value: 'query_param', label: 'Query Parameter' }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let mappings = $state<SSOAttributeMapping[]>([]);
	let availableSystems = $state<CatalogSystem[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let formData = $state({
		claim_path: '',
		target_header: '',
		target_type: 'header' as 'header' | 'query_param',
		system_filter: '',
		transform: ''
	});
	let saving = $state(false);
	let allSystems = $state(true);

	// Delete confirmation
	let deletingId = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadMappings() {
		loading = true;
		error = '';
		try {
			mappings = await apiJson<SSOAttributeMapping[]>('/admin/sso-mappings');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load SSO mappings';
		} finally {
			loading = false;
		}
	}

	async function loadSystems() {
		try {
			availableSystems = await apiJson<CatalogSystem[]>('/catalog/systems');
		} catch {
			/* silent — systems are optional enhancement */
		}
	}

	$effect(() => {
		loadMappings();
		loadSystems();
	});

	// -----------------------------------------------------------------------
	// Form actions
	// -----------------------------------------------------------------------

	function openAddForm() {
		editingId = null;
		formData = {
			claim_path: '',
			target_header: '',
			target_type: 'header',
			system_filter: '',
			transform: ''
		};
		allSystems = true;
		showForm = true;
	}

	function openEditForm(mapping: SSOAttributeMapping) {
		editingId = mapping.id;
		formData = {
			claim_path: mapping.claim_path,
			target_header: mapping.target_header,
			target_type: mapping.target_type,
			system_filter: mapping.system_filter || '',
			transform: mapping.transform || ''
		};
		allSystems = !mapping.system_filter;
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editingId = null;
	}

	async function submitForm() {
		saving = true;
		error = '';

		const payload = {
			claim_path: formData.claim_path,
			target_header: formData.target_header,
			target_type: formData.target_type,
			system_filter: allSystems ? null : formData.system_filter || null,
			transform: formData.transform || null
		};

		try {
			if (editingId) {
				await apiJson(`/admin/sso-mappings/${editingId}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/admin/sso-mappings', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			showForm = false;
			editingId = null;
			await loadMappings();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save mapping';
		} finally {
			saving = false;
		}
	}

	async function deleteMapping(id: string) {
		error = '';
		try {
			await apiFetch(`/admin/sso-mappings/${id}`, { method: 'DELETE' });
			deletingId = null;
			await loadMappings();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete mapping';
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function systemName(systemId: string | null): string {
		if (!systemId) return 'All systems';
		const sys = availableSystems.find((s) => s.id === systemId);
		return sys?.name || systemId;
	}

	function transformLabel(transform: string | null): string {
		if (!transform) return 'None';
		if (transform.startsWith('prefix:')) return `Prefix: ${transform.slice(7)}`;
		return TRANSFORMS.find((t) => t.value === transform)?.label ?? transform;
	}
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">SSO Attribute Mappings</h1>
				<p class="text-sm text-text-secondary">
					Map SSO claims to HTTP headers for API impersonation
				</p>
			</div>
			<button
				type="button"
				onclick={openAddForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Add Mapping
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
				Add Mapping
			</button>
		</div>
	{/if}

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
				<h3 class="text-sm font-semibold text-text-primary">
					{editingId ? 'Edit Mapping' : 'New SSO Attribute Mapping'}
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
					<span class="text-xs font-medium text-text-secondary">Claim Path</span>
					<input
						type="text"
						bind:value={formData.claim_path}
						required
						placeholder="e.g. employee_id or custom_claims.hr_id"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Target Header</span>
					<input
						type="text"
						bind:value={formData.target_header}
						required
						placeholder="e.g. X-Employee-ID"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Target Type</span>
					<select
						bind:value={formData.target_type}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						{#each TARGET_TYPES as tt}
							<option value={tt.value}>{tt.label}</option>
						{/each}
					</select>
				</label>

				<div class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						System Filter
						<span class="text-text-secondary/60">(optional)</span>
					</span>
					<label class="flex items-center gap-2 py-1">
						<input
							type="checkbox"
							bind:checked={allSystems}
							class="rounded border-border text-accent focus:ring-accent"
						/>
						<span class="text-sm text-text-primary">Apply to all systems</span>
					</label>
					{#if !allSystems}
						<select
							bind:value={formData.system_filter}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						>
							<option value="">Select a system...</option>
							{#each availableSystems as sys}
								<option value={sys.id}>{sys.name}</option>
							{/each}
						</select>
					{/if}
				</div>

				<label class="col-span-2 flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">
						Transform
						<span class="text-text-secondary/60">(optional)</span>
					</span>
					<input
						type="text"
						bind:value={formData.transform}
						placeholder="e.g. uppercase, lowercase, prefix:EMP-, base64"
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
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Claim Path
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Target Header
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Type
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								System Filter
							</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">
								Transform
							</th>
							<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary">
								Actions
							</th>
						</tr>
					</thead>
					<tbody>
						{#each mappings as mapping, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2 font-mono text-xs text-text-primary">
									{mapping.claim_path}
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-primary">
									{mapping.target_header}
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										{mapping.target_type}
									</span>
								</td>
								<td class="px-4 py-2 font-mono text-xs text-text-secondary">
									{systemName(mapping.system_filter)}
								</td>
								<td class="px-4 py-2 text-xs text-text-secondary">
									{transformLabel(mapping.transform)}
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={() => openEditForm(mapping)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Edit"
										>
											<Pencil size={14} />
										</button>
										{#if deletingId === mapping.id}
											<button
												type="button"
												onclick={() => deleteMapping(mapping.id)}
												class="rounded bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger transition-colors hover:bg-danger/20"
											>
												Confirm
											</button>
											<button
												type="button"
												onclick={() => (deletingId = null)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
												title="Cancel"
											>
												<X size={14} />
											</button>
										{:else}
											<button
												type="button"
												onclick={() => (deletingId = mapping.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										{/if}
									</div>
								</td>
							</tr>
						{:else}
							<tr>
								<td
									colspan="6"
									class="px-4 py-8 text-center text-sm text-text-secondary"
								>
									<div class="flex flex-col items-center gap-2">
										<ArrowLeftRight
											size={32}
											strokeWidth={1}
											class="text-text-secondary/40"
										/>
										No SSO attribute mappings configured. Add one to forward SSO
										claims as API headers.
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
