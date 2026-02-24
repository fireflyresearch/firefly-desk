<!--
  UsersRolesManager.svelte - Unified user and role management.

  Combines UserManager and RoleManager into a single page
  with a tab bar for navigation between the two views.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Users, ShieldCheck } from 'lucide-svelte';
	import UserManager from './UserManager.svelte';
	import RoleManager from './RoleManager.svelte';

	let activeTab = $state<'users' | 'roles'>('users');
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div>
		<h1 class="text-lg font-semibold text-text-primary">Users & Roles</h1>
		<p class="text-sm text-text-secondary">
			View system users and manage role-based access control
		</p>
	</div>

	<!-- Tab bar -->
	<div class="flex gap-1 border-b border-border">
		<button
			type="button"
			onclick={() => (activeTab = 'users')}
			class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'users'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			<Users size={14} />
			Users
		</button>
		<button
			type="button"
			onclick={() => (activeTab = 'roles')}
			class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'roles'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			<ShieldCheck size={14} />
			Roles
		</button>
	</div>

	<!-- Tab content -->
	<div class="flex-1 overflow-y-auto">
		{#if activeTab === 'users'}
			<UserManager embedded={true} />
		{:else}
			<RoleManager embedded={true} />
		{/if}
	</div>
</div>
