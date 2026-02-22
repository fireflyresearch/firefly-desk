<!--
  UserManager.svelte - Admin user management table.

  Displays a list of users derived from system activity with display name,
  email, role badges, and last active timestamp.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Users, Loader2, RefreshCw } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

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

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let users = $state<UserSummary[]>([]);
	let loading = $state(true);
	let error = $state('');

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

	// Initial load
	$effect(() => {
		loadUsers();
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

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
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

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
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
							</tr>
						{:else}
							<tr>
								<td colspan="6" class="px-4 py-8 text-center text-sm text-text-secondary">
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
	{/if}
</div>
