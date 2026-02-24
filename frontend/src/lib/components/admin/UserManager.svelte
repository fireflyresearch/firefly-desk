<!--
  UserManager.svelte - Admin user management table.

  Displays a list of users derived from system activity with display name,
  email, role badges, last active timestamp, and role assignment controls.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Users, Loader2, RefreshCw, ShieldCheck, X } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

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

	interface UserSummary {
		user_id: string;
		display_name: string | null;
		email: string | null;
		roles: string[];
		conversation_count: number;
		last_active: string | null;
	}

	interface RoleRecord {
		id: string;
		name: string;
		display_name: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let users = $state<UserSummary[]>([]);
	let loading = $state(true);
	let error = $state('');
	let allRoles = $state<RoleRecord[]>([]);
	let managingRolesUser = $state<UserSummary | null>(null);
	let selectedRoleIds = $state<Set<string>>(new Set());
	let savingRoles = $state(false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadUsers() {
		loading = true;
		error = '';
		try {
			users = await apiJson<UserSummary[]>('/admin/users');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load users';
		} finally {
			loading = false;
		}
	}

	async function loadRoles() {
		try {
			allRoles = await apiJson<RoleRecord[]>('/admin/roles');
		} catch {
			// Roles are supplementary
		}
	}

	async function openRolePanel(user: UserSummary) {
		managingRolesUser = user;
		try {
			const roleIds = await apiJson<string[]>(`/admin/users/${user.user_id}/roles`);
			selectedRoleIds = new Set(roleIds);
		} catch {
			selectedRoleIds = new Set();
		}
	}

	function toggleRole(roleId: string) {
		const next = new Set(selectedRoleIds);
		if (next.has(roleId)) {
			next.delete(roleId);
		} else {
			next.add(roleId);
		}
		selectedRoleIds = next;
	}

	async function saveRoles() {
		if (!managingRolesUser) return;
		savingRoles = true;
		error = '';
		try {
			await apiJson(`/admin/users/${managingRolesUser.user_id}/roles`, {
				method: 'PUT',
				body: JSON.stringify({ role_ids: [...selectedRoleIds] })
			});
			managingRolesUser = null;
			await loadUsers();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save roles';
		} finally {
			savingRoles = false;
		}
	}

	// Initial load
	$effect(() => {
		loadUsers();
		loadRoles();
	});

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function roleBadgeClass(role: string): string {
		switch (role) {
			case 'admin':
				return 'bg-accent/10 text-accent';
			case 'operator':
				return 'bg-success/10 text-success';
			default:
				return 'bg-surface-secondary text-text-secondary';
		}
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '--';
		try {
			const date = new Date(iso);
			return date.toLocaleDateString(undefined, {
				month: 'short',
				day: 'numeric',
				year: 'numeric',
				hour: '2-digit',
				minute: '2-digit'
			});
		} catch {
			return iso;
		}
	}
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Users</h1>
				<p class="text-sm text-text-secondary">Users identified from system activity</p>
			</div>
			<button
				type="button"
				onclick={loadUsers}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			>
				<RefreshCw size={14} />
				Refresh
			</button>
		</div>
	{:else}
		<div class="flex justify-end">
			<button
				type="button"
				onclick={loadUsers}
				class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			>
				<RefreshCw size={14} />
				Refresh
			</button>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Table + Side Panel -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="flex gap-4">
			<div class="min-w-0 flex-1 rounded-lg border border-border bg-surface">
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-border bg-surface-secondary">
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">User ID</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Display Name
								</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Email</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Roles</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Conversations
								</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Last Active
								</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Actions
								</th>
							</tr>
						</thead>
						<tbody>
							{#each users as user, i}
								<tr
									class="border-b border-border last:border-b-0 {i % 2 === 1
										? 'bg-surface-secondary/50'
										: ''}"
								>
									<td class="px-4 py-2 font-mono text-xs text-text-primary">
										{user.user_id}
									</td>
									<td class="px-4 py-2 text-text-primary">
										{user.display_name ?? '--'}
									</td>
									<td class="px-4 py-2 text-text-secondary">
										{user.email ?? '--'}
									</td>
									<td class="px-4 py-2">
										{#if user.roles.length > 0}
											<div class="flex flex-wrap gap-1">
												{#each user.roles as role}
													<span
														class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {roleBadgeClass(role)}"
													>
														{role}
													</span>
												{/each}
											</div>
										{:else}
											<span class="text-xs text-text-secondary">--</span>
										{/if}
									</td>
									<td class="px-4 py-2 text-text-secondary">
										{user.conversation_count}
									</td>
									<td class="px-4 py-2 text-xs text-text-secondary">
										{formatDate(user.last_active)}
									</td>
									<td class="px-4 py-2">
										<button
											type="button"
											onclick={() => openRolePanel(user)}
											class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
										>
											<ShieldCheck size={12} />
											Manage Roles
										</button>
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="7" class="px-4 py-8 text-center text-sm text-text-secondary">
										<div class="flex flex-col items-center gap-2">
											<Users size={24} class="text-text-secondary/40" />
											<p>No users found. Activity-based user discovery requires conversations or audit events.</p>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			{#if managingRolesUser}
				<div class="flex w-72 shrink-0 flex-col rounded-lg border border-border bg-surface">
					<div class="flex items-center justify-between border-b border-border px-3 py-2.5">
						<h4 class="text-sm font-semibold text-text-primary">
							Assign Roles
						</h4>
						<button
							type="button"
							onclick={() => (managingRolesUser = null)}
							class="rounded p-1 text-text-secondary hover:text-text-primary"
						>
							<X size={14} />
						</button>
					</div>
					<div class="p-3">
						<p class="mb-3 text-xs text-text-secondary">
							{managingRolesUser.display_name ?? managingRolesUser.user_id}
						</p>
						<div class="flex flex-col gap-2">
							{#each allRoles as role}
								<label class="flex items-center gap-2 text-sm">
									<input
										type="checkbox"
										checked={selectedRoleIds.has(role.id)}
										onchange={() => toggleRole(role.id)}
										class="accent-accent"
									/>
									<span class="text-text-primary">{role.display_name}</span>
								</label>
							{/each}
						</div>
					</div>
					<div class="border-t border-border p-3">
						<button
							type="button"
							onclick={saveRoles}
							disabled={savingRoles}
							class="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
						>
							{#if savingRoles}
								<Loader2 size={14} class="animate-spin" />
							{/if}
							Save Roles
						</button>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
