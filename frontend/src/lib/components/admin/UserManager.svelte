<!--
  UserManager.svelte - Admin user management table with full CRUD.

  Displays a list of users with create, edit, deactivate, reset-password,
  and SSO identity management. Role assignment uses the side-panel pattern.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Users,
		Loader2,
		RefreshCw,
		ShieldCheck,
		X,
		UserPlus,
		Pencil,
		Trash2,
		Key,
		Link2,
		Unlink,
		ChevronDown,
		ChevronRight,
		Save,
		Ban,
		CheckCircle
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

	interface UserSummary {
		user_id: string;
		display_name: string | null;
		email: string | null;
		roles: string[];
		conversation_count: number;
		last_active: string | null;
	}

	interface LocalUserResponse {
		id: string;
		username: string;
		email: string;
		display_name: string;
		role: string;
		is_active: boolean;
		created_at: string;
		updated_at: string;
		last_login_at: string | null;
	}

	interface SSOIdentityResponse {
		id: string;
		provider_id: string;
		provider_name: string | null;
		subject: string;
		email: string | null;
		local_user_id: string;
		linked_at: string;
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

	// Role assignment side-panel
	let managingRolesUser = $state<UserSummary | null>(null);
	let selectedRoleIds = $state<Set<string>>(new Set());
	let savingRoles = $state(false);

	// Create user form
	let showAddForm = $state(false);
	let creatingUser = $state(false);
	let newUser = $state({
		username: '',
		email: '',
		display_name: '',
		password: '',
		role: 'user'
	});

	// Inline edit (expanded row)
	let expandedUserId = $state<string | null>(null);
	let editData = $state<{
		email: string;
		display_name: string;
		is_active: boolean;
	}>({ email: '', display_name: '', is_active: true });
	let editLocalUser = $state<LocalUserResponse | null>(null);
	let savingEdit = $state(false);
	let loadingDetail = $state(false);

	// Reset password
	let showResetPassword = $state(false);
	let resetPasswordValue = $state('');
	let resettingPassword = $state(false);

	// SSO Identities
	let ssoIdentities = $state<SSOIdentityResponse[]>([]);
	let loadingSso = $state(false);
	let showSsoSection = $state(false);

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

	// Initial load
	$effect(() => {
		loadUsers();
		loadRoles();
	});

	// -----------------------------------------------------------------------
	// Create user
	// -----------------------------------------------------------------------

	function resetNewUserForm() {
		newUser = { username: '', email: '', display_name: '', password: '', role: 'user' };
	}

	async function createUser() {
		if (!newUser.username || !newUser.email || !newUser.password) {
			error = 'Username, email, and password are required.';
			return;
		}
		creatingUser = true;
		error = '';
		try {
			await apiJson<LocalUserResponse>('/admin/users', {
				method: 'POST',
				body: JSON.stringify(newUser)
			});
			resetNewUserForm();
			showAddForm = false;
			await loadUsers();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create user';
		} finally {
			creatingUser = false;
		}
	}

	// -----------------------------------------------------------------------
	// Expand / Edit user
	// -----------------------------------------------------------------------

	async function toggleExpand(user: UserSummary) {
		if (expandedUserId === user.user_id) {
			expandedUserId = null;
			editLocalUser = null;
			showResetPassword = false;
			showSsoSection = false;
			return;
		}

		expandedUserId = user.user_id;
		showResetPassword = false;
		showSsoSection = false;
		resetPasswordValue = '';
		ssoIdentities = [];
		loadingDetail = true;

		try {
			const detail = await apiJson<LocalUserResponse>(`/admin/users/${user.user_id}`);
			editLocalUser = detail;
			editData = {
				email: detail.email,
				display_name: detail.display_name,
				is_active: detail.is_active
			};
		} catch {
			// User might not be a local user (activity-derived)
			editLocalUser = null;
			editData = {
				email: user.email ?? '',
				display_name: user.display_name ?? '',
				is_active: true
			};
		} finally {
			loadingDetail = false;
		}
	}

	async function saveEdit() {
		if (!expandedUserId || !editLocalUser) return;
		savingEdit = true;
		error = '';
		try {
			await apiJson<LocalUserResponse>(`/admin/users/${expandedUserId}`, {
				method: 'PUT',
				body: JSON.stringify({
					email: editData.email,
					display_name: editData.display_name,
					is_active: editData.is_active
				})
			});
			expandedUserId = null;
			editLocalUser = null;
			await loadUsers();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update user';
		} finally {
			savingEdit = false;
		}
	}

	// -----------------------------------------------------------------------
	// Deactivate user
	// -----------------------------------------------------------------------

	async function deactivateUser(userId: string) {
		error = '';
		try {
			await apiFetch(`/admin/users/${userId}`, { method: 'DELETE' });
			expandedUserId = null;
			editLocalUser = null;
			await loadUsers();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to deactivate user';
		}
	}

	// -----------------------------------------------------------------------
	// Reset password
	// -----------------------------------------------------------------------

	async function resetPassword() {
		if (!expandedUserId || !resetPasswordValue) {
			error = 'Password is required.';
			return;
		}
		resettingPassword = true;
		error = '';
		try {
			await apiJson(`/admin/users/${expandedUserId}/reset-password`, {
				method: 'POST',
				body: JSON.stringify({ password: resetPasswordValue })
			});
			resetPasswordValue = '';
			showResetPassword = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to reset password';
		} finally {
			resettingPassword = false;
		}
	}

	// -----------------------------------------------------------------------
	// SSO Identities
	// -----------------------------------------------------------------------

	async function loadSsoIdentities(userId: string) {
		loadingSso = true;
		try {
			ssoIdentities = await apiJson<SSOIdentityResponse[]>(
				`/admin/users/${userId}/sso-identities`
			);
		} catch {
			ssoIdentities = [];
		} finally {
			loadingSso = false;
		}
	}

	async function toggleSsoSection() {
		showSsoSection = !showSsoSection;
		if (showSsoSection && expandedUserId) {
			await loadSsoIdentities(expandedUserId);
		}
	}

	async function unlinkSsoIdentity(userId: string, identityId: string) {
		error = '';
		try {
			await apiFetch(`/admin/users/${userId}/sso-identities/${identityId}`, {
				method: 'DELETE'
			});
			await loadSsoIdentities(userId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to unlink SSO identity';
		}
	}

	// -----------------------------------------------------------------------
	// Role assignment side-panel
	// -----------------------------------------------------------------------

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

	const inputClass =
		'w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent';
</script>

<div class="flex h-full flex-col gap-4 overflow-y-auto" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Users</h1>
				<p class="text-sm text-text-secondary">
					Manage user accounts, roles, and SSO identities
				</p>
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					onclick={() => {
						showAddForm = !showAddForm;
						if (showAddForm) resetNewUserForm();
					}}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90"
				>
					<UserPlus size={14} />
					Add User
				</button>
				<button
					type="button"
					onclick={loadUsers}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<RefreshCw size={14} />
					Refresh
				</button>
			</div>
		</div>
	{:else}
		<div class="flex justify-end gap-2">
			<button
				type="button"
				onclick={() => {
					showAddForm = !showAddForm;
					if (showAddForm) resetNewUserForm();
				}}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90"
			>
				<UserPlus size={14} />
				Add User
			</button>
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
		<div
			class="flex items-center justify-between rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<span>{error}</span>
			<button
				type="button"
				onclick={() => (error = '')}
				class="ml-2 rounded p-0.5 hover:bg-danger/10"
			>
				<X size={14} />
			</button>
		</div>
	{/if}

	<!-- Add User Form -->
	{#if showAddForm}
		<div class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm">
			<h3 class="mb-3 text-sm font-semibold text-text-primary">Create New User</h3>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<input
					bind:value={newUser.username}
					placeholder="Username"
					class={inputClass}
				/>
				<input
					bind:value={newUser.email}
					placeholder="Email"
					type="email"
					class={inputClass}
				/>
				<input
					bind:value={newUser.display_name}
					placeholder="Display Name"
					class={inputClass}
				/>
				<input
					bind:value={newUser.password}
					placeholder="Password"
					type="password"
					class={inputClass}
				/>
				<select bind:value={newUser.role} class={inputClass}>
					<option value="user">User</option>
					<option value="admin">Admin</option>
					<option value="operator">Operator</option>
				</select>
			</div>
			<div class="mt-4 flex gap-2">
				<button
					type="button"
					onclick={createUser}
					disabled={creatingUser}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
				>
					{#if creatingUser}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<UserPlus size={14} />
					{/if}
					Create
				</button>
				<button
					type="button"
					onclick={() => {
						showAddForm = false;
						resetNewUserForm();
					}}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-4 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					Cancel
				</button>
			</div>
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
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									User ID
								</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Display Name
								</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Email
								</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">
									Roles
								</th>
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
								<!-- User row -->
								<tr
									class="cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-surface-hover {i %
										2 ===
									1
										? 'bg-surface-secondary/50'
										: ''} {expandedUserId === user.user_id
										? 'bg-accent/5'
										: ''}"
									onclick={() => toggleExpand(user)}
								>
									<td class="px-4 py-2 font-mono text-xs text-text-primary">
										<div class="flex items-center gap-1.5">
											{#if expandedUserId === user.user_id}
												<ChevronDown size={12} class="text-text-secondary" />
											{:else}
												<ChevronRight
													size={12}
													class="text-text-secondary"
												/>
											{/if}
											<span class="truncate" title={user.user_id}>
												{user.user_id.length > 12
													? user.user_id.slice(0, 12) + '...'
													: user.user_id}
											</span>
										</div>
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
											onclick={(e: MouseEvent) => {
												e.stopPropagation();
												openRolePanel(user);
											}}
											class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
										>
											<ShieldCheck size={12} />
											Roles
										</button>
									</td>
								</tr>

								<!-- Expanded edit panel -->
								{#if expandedUserId === user.user_id}
									<tr>
										<td colspan="7" class="border-b border-border bg-surface-secondary/30 p-0">
											<div class="px-6 py-4">
												{#if loadingDetail}
													<div class="flex items-center gap-2 py-4">
														<Loader2
															size={16}
															class="animate-spin text-text-secondary"
														/>
														<span class="text-sm text-text-secondary"
															>Loading user details...</span
														>
													</div>
												{:else if editLocalUser}
													<!-- Editable local user -->
													<div class="space-y-4">
														<div class="flex items-center gap-2">
															<Pencil
																size={14}
																class="text-text-secondary"
															/>
															<h4
																class="text-sm font-semibold text-text-primary"
															>
																Edit User: {editLocalUser.username}
															</h4>
															{#if !editData.is_active}
																<span
																	class="inline-flex items-center gap-1 rounded-full bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger"
																>
																	<Ban size={10} />
																	Inactive
																</span>
															{:else}
																<span
																	class="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
																>
																	<CheckCircle size={10} />
																	Active
																</span>
															{/if}
														</div>

														<!-- Edit fields -->
														<div
															class="grid grid-cols-1 gap-3 sm:grid-cols-3"
														>
															<div>
																<label
																	for="edit-email"
																	class="mb-1 block text-xs font-medium text-text-secondary"
																	>Email</label
																>
																<input
																	id="edit-email"
																	bind:value={editData.email}
																	type="email"
																	class={inputClass}
																/>
															</div>
															<div>
																<label
																	for="edit-display-name"
																	class="mb-1 block text-xs font-medium text-text-secondary"
																	>Display Name</label
																>
																<input
																	id="edit-display-name"
																	bind:value={
																		editData.display_name
																	}
																	class={inputClass}
																/>
															</div>
															<div>
																<label
																	for="edit-is-active"
																	class="mb-1 block text-xs font-medium text-text-secondary"
																	>Status</label
																>
																<label
																	class="mt-1 flex items-center gap-2 text-sm"
																>
																	<input
																		id="edit-is-active"
																		type="checkbox"
																		bind:checked={
																			editData.is_active
																		}
																		class="accent-accent"
																	/>
																	<span class="text-text-primary"
																		>Active</span
																	>
																</label>
															</div>
														</div>

														<!-- Save / Cancel / Deactivate buttons -->
														<div
															class="flex items-center gap-2 border-t border-border pt-3"
														>
															<button
																type="button"
																onclick={saveEdit}
																disabled={savingEdit}
																class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
															>
																{#if savingEdit}
																	<Loader2
																		size={14}
																		class="animate-spin"
																	/>
																{:else}
																	<Save size={14} />
																{/if}
																Save Changes
															</button>
															<button
																type="button"
																onclick={() => {
																	expandedUserId = null;
																	editLocalUser = null;
																}}
																class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
															>
																Cancel
															</button>
															<div class="flex-1"></div>
															<button
																type="button"
																onclick={() =>
																	(showResetPassword =
																		!showResetPassword)}
																class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
															>
																<Key size={14} />
																Reset Password
															</button>
															<button
																type="button"
																onclick={toggleSsoSection}
																class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
															>
																<Link2 size={14} />
																SSO Identities
															</button>
															{#if editData.is_active}
																<button
																	type="button"
																	onclick={() =>
																		deactivateUser(
																			user.user_id
																		)}
																	class="inline-flex items-center gap-1.5 rounded-md border border-danger/30 px-3 py-1.5 text-sm text-danger transition-colors hover:bg-danger/5"
																>
																	<Trash2 size={14} />
																	Deactivate
																</button>
															{/if}
														</div>

														<!-- Reset Password section -->
														{#if showResetPassword}
															<div
																class="rounded-md border border-border bg-surface p-3"
															>
																<h5
																	class="mb-2 text-xs font-semibold text-text-primary"
																>
																	Reset Password
																</h5>
																<div class="flex gap-2">
																	<input
																		bind:value={
																			resetPasswordValue
																		}
																		type="password"
																		placeholder="New password"
																		class={inputClass}
																	/>
																	<button
																		type="button"
																		onclick={resetPassword}
																		disabled={resettingPassword}
																		class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
																	>
																		{#if resettingPassword}
																			<Loader2
																				size={14}
																				class="animate-spin"
																			/>
																		{:else}
																			<Key size={14} />
																		{/if}
																		Reset
																	</button>
																	<button
																		type="button"
																		onclick={() => {
																			showResetPassword =
																				false;
																			resetPasswordValue = '';
																		}}
																		class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
																	>
																		Cancel
																	</button>
																</div>
															</div>
														{/if}

														<!-- SSO Identities section -->
														{#if showSsoSection}
															<div
																class="rounded-md border border-border bg-surface p-3"
															>
																<h5
																	class="mb-2 text-xs font-semibold text-text-primary"
																>
																	Linked SSO Identities
																</h5>
																{#if loadingSso}
																	<div
																		class="flex items-center gap-2 py-2"
																	>
																		<Loader2
																			size={14}
																			class="animate-spin text-text-secondary"
																		/>
																		<span
																			class="text-xs text-text-secondary"
																			>Loading...</span
																		>
																	</div>
																{:else if ssoIdentities.length === 0}
																	<p
																		class="py-2 text-xs text-text-secondary"
																	>
																		No SSO identities linked to
																		this user.
																	</p>
																{:else}
																	<div class="space-y-2">
																		{#each ssoIdentities as identity}
																			<div
																				class="flex items-center justify-between rounded-md border border-border bg-surface-secondary/50 px-3 py-2"
																			>
																				<div
																					class="flex items-center gap-2"
																				>
																					<Link2
																						size={12}
																						class="text-text-secondary"
																					/>
																					<div>
																						<span
																							class="text-sm font-medium text-text-primary"
																						>
																							{identity.provider_name ??
																								identity.provider_id}
																						</span>
																						<span
																							class="ml-2 text-xs text-text-secondary"
																						>
																							{identity.subject}
																						</span>
																						{#if identity.email}
																							<span
																								class="ml-2 text-xs text-text-secondary"
																							>
																								({identity.email})
																							</span>
																						{/if}
																					</div>
																				</div>
																				<button
																					type="button"
																					onclick={() =>
																						unlinkSsoIdentity(
																							user.user_id,
																							identity.id
																						)}
																					class="inline-flex items-center gap-1 rounded-md border border-danger/30 px-2 py-1 text-xs text-danger transition-colors hover:bg-danger/5"
																				>
																					<Unlink
																						size={12}
																					/>
																					Unlink
																				</button>
																			</div>
																		{/each}
																	</div>
																{/if}
															</div>
														{/if}
													</div>
												{:else}
													<!-- Non-local (activity-derived) user -->
													<div class="space-y-2">
														<p class="text-sm text-text-secondary">
															This user was discovered from system
															activity and is not a locally managed
															account. Only role assignment is
															available.
														</p>
														<button
															type="button"
															onclick={() => {
																expandedUserId = null;
															}}
															class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
														>
															Close
														</button>
													</div>
												{/if}
											</div>
										</td>
									</tr>
								{/if}
							{:else}
								<tr>
									<td
										colspan="7"
										class="px-4 py-8 text-center text-sm text-text-secondary"
									>
										<div class="flex flex-col items-center gap-2">
											<Users size={24} class="text-text-secondary/40" />
											<p>No users found. Create a user or wait for activity-based discovery.</p>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<!-- Role assignment side panel -->
			{#if managingRolesUser}
				<div
					class="flex w-72 shrink-0 flex-col rounded-lg border border-border bg-surface"
				>
					<div
						class="flex items-center justify-between border-b border-border px-3 py-2.5"
					>
						<h4 class="text-sm font-semibold text-text-primary">Assign Roles</h4>
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
