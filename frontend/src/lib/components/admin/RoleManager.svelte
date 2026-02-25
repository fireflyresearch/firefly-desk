<!--
  RoleManager.svelte - RBAC role management admin panel.

  Displays a table of roles with create/edit/delete actions.
  Includes a permission reference panel and edit form with
  permission checkboxes grouped by resource.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Trash2,
		X,
		Save,
		Loader2,
		Pencil,
		Shield,
		Lock,
		ChevronDown,
		ChevronRight,
		Info
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

	interface RoleRecord {
		id: string;
		name: string;
		display_name: string;
		description: string;
		permissions: string[];
		is_builtin: boolean;
		created_at: string | null;
		updated_at: string | null;
	}

	interface PermissionInfo {
		value: string;
		name: string;
		resource: string;
		action: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let roles = $state<RoleRecord[]>([]);
	let permissions = $state<PermissionInfo[]>([]);
	let loadingRoles = $state(true);
	let loadingPermissions = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingRole = $state<RoleRecord | null>(null);
	let saving = $state(false);
	let formData = $state({
		name: '',
		display_name: '',
		description: '',
		permissions: [] as string[]
	});

	// Active tab
	let activeTab = $state<'roles' | 'permissions'>('roles');

	// Expanded resource groups in permission checkboxes
	let expandedGroups = $state<Set<string>>(new Set());

	// -----------------------------------------------------------------------
	// Derived: group permissions by resource
	// -----------------------------------------------------------------------

	let permissionGroups = $derived.by(() => {
		const groups: Record<string, PermissionInfo[]> = {};
		for (const perm of permissions) {
			if (!groups[perm.resource]) {
				groups[perm.resource] = [];
			}
			groups[perm.resource].push(perm);
		}
		return groups;
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadRoles() {
		loadingRoles = true;
		try {
			roles = await apiJson<RoleRecord[]>('/admin/roles');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load roles';
		} finally {
			loadingRoles = false;
		}
	}

	async function loadPermissions() {
		loadingPermissions = true;
		try {
			permissions = await apiJson<PermissionInfo[]>('/admin/permissions');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load permissions';
		} finally {
			loadingPermissions = false;
		}
	}

	$effect(() => {
		loadRoles();
		loadPermissions();
	});

	// -----------------------------------------------------------------------
	// Form actions
	// -----------------------------------------------------------------------

	function openCreateForm() {
		editingRole = null;
		formData = {
			name: '',
			display_name: '',
			description: '',
			permissions: []
		};
		expandedGroups = new Set(Object.keys(permissionGroups));
		showForm = true;
	}

	function openEditForm(role: RoleRecord) {
		editingRole = role;
		formData = {
			name: role.name,
			display_name: role.display_name,
			description: role.description,
			permissions: [...role.permissions]
		};
		expandedGroups = new Set(Object.keys(permissionGroups));
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editingRole = null;
	}

	function togglePermission(value: string) {
		if (formData.permissions.includes(value)) {
			formData.permissions = formData.permissions.filter((p) => p !== value);
		} else {
			formData.permissions = [...formData.permissions, value];
		}
	}

	function toggleGroup(resource: string) {
		const next = new Set(expandedGroups);
		if (next.has(resource)) {
			next.delete(resource);
		} else {
			next.add(resource);
		}
		expandedGroups = next;
	}

	function toggleAllInGroup(resource: string) {
		const group = permissionGroups[resource] ?? [];
		const allSelected = group.every((p) => formData.permissions.includes(p.value));
		if (allSelected) {
			// Deselect all in group
			const groupValues = new Set(group.map((p) => p.value));
			formData.permissions = formData.permissions.filter((p) => !groupValues.has(p));
		} else {
			// Select all in group
			const current = new Set(formData.permissions);
			for (const p of group) {
				current.add(p.value);
			}
			formData.permissions = [...current];
		}
	}

	async function submitForm() {
		saving = true;
		error = '';

		try {
			if (editingRole) {
				// Update existing role
				await apiJson(`/admin/roles/${editingRole.id}`, {
					method: 'PUT',
					body: JSON.stringify({
						display_name: formData.display_name,
						description: formData.description,
						permissions: formData.permissions
					})
				});
			} else {
				// Create new role
				await apiJson('/admin/roles', {
					method: 'POST',
					body: JSON.stringify(formData)
				});
			}
			showForm = false;
			editingRole = null;
			await loadRoles();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save role';
		} finally {
			saving = false;
		}
	}

	async function deleteRole(id: string, name: string) {
		if (!confirm(`Delete role "${name}"? This cannot be undone.`)) return;
		error = '';
		try {
			await apiFetch(`/admin/roles/${id}`, { method: 'DELETE' });
			await loadRoles();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete role';
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '--';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	function capitalize(str: string): string {
		return str.charAt(0).toUpperCase() + str.slice(1);
	}
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Roles &amp; Permissions</h1>
				<p class="text-sm text-text-secondary">
					Manage RBAC roles and view available permissions
				</p>
			</div>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Tab bar -->
	<div class="flex gap-1 border-b border-border">
		<button
			type="button"
			onclick={() => (activeTab = 'roles')}
			class="px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'roles'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			Roles
		</button>
		<button
			type="button"
			onclick={() => (activeTab = 'permissions')}
			class="px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'permissions'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			Permission Reference
		</button>
	</div>

	<!-- ================================================================= -->
	<!-- Roles Tab                                                          -->
	<!-- ================================================================= -->
	{#if activeTab === 'roles'}
		<!-- New role button -->
		<div class="flex justify-end">
			<button
				type="button"
				onclick={openCreateForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				New Role
			</button>
		</div>

		<!-- Create/edit form -->
		{#if showForm}
			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="mb-3 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-text-primary">
						{editingRole ? `Edit Role: ${editingRole.display_name}` : 'Create Role'}
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
					class="flex flex-col gap-3"
				>
					<div class="grid grid-cols-2 gap-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Name (identifier)</span>
							<input
								type="text"
								bind:value={formData.name}
								required
								disabled={editingRole !== null}
								placeholder="e.g. support-agent"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent disabled:opacity-50"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Display Name</span>
							<input
								type="text"
								bind:value={formData.display_name}
								required
								placeholder="e.g. Support Agent"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>
					</div>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Description</span>
						<input
							type="text"
							bind:value={formData.description}
							placeholder="Brief description of this role's purpose"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<!-- Permission checkboxes grouped by resource -->
					<div class="flex flex-col gap-2">
						<span class="text-xs font-medium text-text-secondary">Permissions</span>
						<div
							class="max-h-64 overflow-y-auto rounded-md border border-border bg-surface-secondary p-2"
						>
							{#each Object.entries(permissionGroups) as [resource, perms]}
								<div class="mb-1">
									<div class="flex w-full items-center gap-1.5 rounded px-2 py-1 text-xs font-semibold uppercase tracking-wide text-text-secondary">
										<button
											type="button"
											onclick={() => toggleGroup(resource)}
											class="flex items-center gap-1.5 hover:text-text-primary"
										>
											{#if expandedGroups.has(resource)}
												<ChevronDown size={12} />
											{:else}
												<ChevronRight size={12} />
											{/if}
											{capitalize(resource)}
										</button>
										<button
											type="button"
											onclick={() => toggleAllInGroup(resource)}
											class="ml-auto text-[10px] font-normal normal-case text-accent hover:text-accent-hover"
										>
											{perms.every((p) => formData.permissions.includes(p.value))
												? 'Deselect all'
												: 'Select all'}
										</button>
									</div>

									{#if expandedGroups.has(resource)}
										<div class="ml-5 flex flex-col gap-0.5 pb-1">
											{#each perms as perm}
												<label
													class="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-surface-hover"
												>
													<input
														type="checkbox"
														checked={formData.permissions.includes(perm.value)}
														onchange={() => togglePermission(perm.value)}
														class="accent-accent"
													/>
													<span class="font-mono text-xs text-text-primary"
														>{perm.value}</span
													>
												</label>
											{/each}
										</div>
									{/if}
								</div>
							{/each}
						</div>
						<p class="text-xs text-text-secondary">
							{formData.permissions.length} permission{formData.permissions.length !== 1
								? 's'
								: ''} selected
						</p>
					</div>

					<div class="flex justify-end gap-2 pt-1">
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
							{editingRole ? 'Update Role' : 'Create Role'}
						</button>
					</div>
				</form>
			</div>
		{/if}

		<!-- Roles table -->
		{#if loadingRoles}
			<div class="flex items-center justify-center py-12">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else}
			<div class="rounded-lg border border-border bg-surface">
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-border bg-surface-secondary">
								<th class="w-8 px-4 py-2"></th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Name</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary"
									>Display Name</th
								>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary"
									>Permissions</th
								>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Created</th>
								<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary"
									>Actions</th
								>
							</tr>
						</thead>
						<tbody>
							{#each roles as role, i}
								<tr
									class="border-b border-border last:border-b-0 {i % 2 === 1
										? 'bg-surface-secondary/50'
										: ''}"
								>
									<td class="px-4 py-2 text-text-secondary">
										<Shield size={14} />
									</td>
									<td class="px-4 py-2 font-medium text-text-primary">
										<span class="font-mono text-xs">{role.name}</span>
									</td>
									<td class="px-4 py-2 text-text-primary">{role.display_name}</td>
									<td class="px-4 py-2">
										<span class="text-xs text-text-secondary">
											{role.permissions.includes('*')
												? 'All (wildcard)'
												: `${role.permissions.length} permission${role.permissions.length !== 1 ? 's' : ''}`}
										</span>
									</td>
									<td class="px-4 py-2">
										{#if role.is_builtin}
											<span
												class="inline-flex items-center gap-1 rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
											>
												<Lock size={10} />
												built-in
											</span>
										{:else}
											<span
												class="rounded bg-accent/10 px-1.5 py-0.5 text-xs text-accent"
											>
												custom
											</span>
										{/if}
									</td>
									<td class="px-4 py-2 text-xs text-text-secondary">
										{formatDate(role.created_at)}
									</td>
									<td class="px-4 py-2">
										<div class="flex items-center gap-1">
											<button
												type="button"
												onclick={() => openEditForm(role)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent"
												title="Edit"
											>
												<Pencil size={14} />
											</button>
											{#if !role.is_builtin}
												<button
													type="button"
													onclick={() => deleteRole(role.id, role.display_name)}
													class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
													title="Delete"
												>
													<Trash2 size={14} />
												</button>
											{:else}
												<span
													class="rounded p-1 text-text-secondary/30"
													title="Built-in roles cannot be deleted"
												>
													<Lock size={14} />
												</span>
											{/if}
										</div>
									</td>
								</tr>
							{:else}
								<tr>
									<td
										colspan="7"
										class="px-4 py-8 text-center text-sm text-text-secondary"
									>
										No roles found. Create one to get started.
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- ================================================================= -->
		<!-- Permission Reference Tab                                           -->
		<!-- ================================================================= -->
	{:else}
		{#if loadingPermissions}
			<div class="flex items-center justify-center py-12">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else}
			<div class="mb-2 flex items-center gap-2 text-xs text-text-secondary">
				<Info size={14} />
				<span
					>All available permissions in the system. Assign these to roles to control
					access.</span
				>
			</div>

			<div class="rounded-lg border border-border bg-surface">
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-border bg-surface-secondary">
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Permission</th
								>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Resource</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Action</th>
							</tr>
						</thead>
						<tbody>
							{#each permissions as perm, i}
								<tr
									class="border-b border-border last:border-b-0 {i % 2 === 1
										? 'bg-surface-secondary/50'
										: ''}"
								>
									<td class="px-4 py-2">
										<span class="font-mono text-xs text-text-primary">{perm.value}</span
										>
									</td>
									<td class="px-4 py-2">
										<span
											class="rounded bg-surface-secondary px-1.5 py-0.5 text-xs capitalize text-text-secondary"
										>
											{perm.resource}
										</span>
									</td>
									<td class="px-4 py-2 text-xs capitalize text-text-secondary">
										{perm.action}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</div>
