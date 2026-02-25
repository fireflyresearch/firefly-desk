<!--
  WorkspaceManager.svelte - CRUD interface for workspace management.

  Displays workspaces in a responsive card grid with create, edit, and
  delete operations via a modal form.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Trash2,
		Pencil,
		Loader2,
		Folder,
		Users,
		Shield,
		X
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Workspace {
		id: string;
		name: string;
		description: string;
		icon: string;
		color: string;
		roles: string[];
		users: string[];
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let workspaces = $state<Workspace[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Modal state
	let showModal = $state(false);
	let saving = $state(false);
	let editingWorkspace = $state<Workspace | null>(null);

	// Form fields
	let formName = $state('');
	let formDescription = $state('');
	let formIcon = $state('folder');
	let formColor = $state('#6366f1');
	let formRoles = $state('');
	let formUsers = $state('');

	// Inline delete confirmation
	let confirmingDeleteId = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadWorkspaces() {
		loading = true;
		error = '';
		try {
			workspaces = await apiJson<Workspace[]>('/workspaces');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load workspaces';
		} finally {
			loading = false;
		}
	}

	// Initial load
	$effect(() => {
		loadWorkspaces();
	});

	// -----------------------------------------------------------------------
	// Modal helpers
	// -----------------------------------------------------------------------

	function openCreateModal() {
		editingWorkspace = null;
		formName = '';
		formDescription = '';
		formIcon = 'folder';
		formColor = '#6366f1';
		formRoles = '';
		formUsers = '';
		showModal = true;
	}

	function openEditModal(workspace: Workspace) {
		editingWorkspace = workspace;
		formName = workspace.name;
		formDescription = workspace.description;
		formIcon = workspace.icon;
		formColor = workspace.color;
		formRoles = workspace.roles.join(', ');
		formUsers = workspace.users.join(', ');
		showModal = true;
	}

	function closeModal() {
		showModal = false;
		editingWorkspace = null;
	}

	// -----------------------------------------------------------------------
	// CRUD actions
	// -----------------------------------------------------------------------

	function parseCommaSeparated(value: string): string[] {
		return value
			.split(',')
			.map((s) => s.trim())
			.filter((s) => s.length > 0);
	}

	async function saveWorkspace() {
		if (!formName.trim()) return;
		saving = true;
		error = '';
		try {
			const body: Record<string, unknown> = {
				name: formName.trim(),
				description: formDescription.trim(),
				icon: formIcon.trim() || 'folder',
				color: formColor.trim() || '#6366f1',
				roles: parseCommaSeparated(formRoles),
				users: parseCommaSeparated(formUsers)
			};

			if (editingWorkspace) {
				await apiJson(`/workspaces/${editingWorkspace.id}`, {
					method: 'PUT',
					body: JSON.stringify(body)
				});
			} else {
				await apiJson('/workspaces', {
					method: 'POST',
					body: JSON.stringify(body)
				});
			}
			closeModal();
			await loadWorkspaces();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save workspace';
		} finally {
			saving = false;
		}
	}

	async function deleteWorkspace(id: string) {
		error = '';
		try {
			await apiFetch(`/workspaces/${id}`, { method: 'DELETE' });
			await loadWorkspaces();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete workspace';
		}
	}

	// -----------------------------------------------------------------------
	// Delete confirmation helpers
	// -----------------------------------------------------------------------

	function startDelete(id: string) {
		confirmingDeleteId = id;
	}

	function cancelDeleteConfirm() {
		confirmingDeleteId = null;
	}

	async function confirmAndDelete(id: string) {
		confirmingDeleteId = null;
		await deleteWorkspace(id);
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex shrink-0 items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Workspaces</h1>
			<p class="text-sm text-text-secondary">Organize resources into isolated workspaces</p>
		</div>
		<button
			type="button"
			onclick={openCreateModal}
			class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			<Plus size={16} />
			Create Workspace
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="shrink-0 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Modal -->
	{#if showModal}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
			onkeydown={(e) => { if (e.key === 'Escape') closeModal(); }}
		>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div
				class="fixed inset-0"
				onclick={closeModal}
			></div>
			<div class="relative z-10 w-full max-w-lg rounded-xl border border-border bg-surface p-6 shadow-xl">
				<div class="mb-4 flex items-center justify-between">
					<h2 class="text-base font-semibold text-text-primary">
						{editingWorkspace ? 'Edit Workspace' : 'Create Workspace'}
					</h2>
					<button
						type="button"
						onclick={closeModal}
						class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
					>
						<X size={16} />
					</button>
				</div>

				<form
					onsubmit={(e) => { e.preventDefault(); saveWorkspace(); }}
					class="flex flex-col gap-4"
				>
					<!-- Name -->
					<div class="flex flex-col gap-1">
						<label for="ws-name" class="text-sm font-medium text-text-primary">
							Name <span class="text-danger">*</span>
						</label>
						<input
							id="ws-name"
							type="text"
							bind:value={formName}
							required
							placeholder="e.g. Engineering"
							class="rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
						/>
					</div>

					<!-- Description -->
					<div class="flex flex-col gap-1">
						<label for="ws-desc" class="text-sm font-medium text-text-primary">
							Description
						</label>
						<textarea
							id="ws-desc"
							bind:value={formDescription}
							rows="3"
							placeholder="Optional description..."
							class="rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
						></textarea>
					</div>

					<!-- Icon & Color (side by side) -->
					<div class="grid grid-cols-2 gap-4">
						<div class="flex flex-col gap-1">
							<label for="ws-icon" class="text-sm font-medium text-text-primary">
								Icon
							</label>
							<input
								id="ws-icon"
								type="text"
								bind:value={formIcon}
								placeholder="folder"
								class="rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label for="ws-color" class="text-sm font-medium text-text-primary">
								Color
							</label>
							<div class="flex items-center gap-2">
								<input
									id="ws-color"
									type="color"
									bind:value={formColor}
									class="h-8 w-8 cursor-pointer rounded border border-border bg-surface-secondary"
								/>
								<input
									type="text"
									bind:value={formColor}
									placeholder="#6366f1"
									class="flex-1 rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
								/>
							</div>
						</div>
					</div>

					<!-- Roles -->
					<div class="flex flex-col gap-1">
						<label for="ws-roles" class="text-sm font-medium text-text-primary">
							Roles
						</label>
						<input
							id="ws-roles"
							type="text"
							bind:value={formRoles}
							placeholder="Comma-separated, e.g. admin, editor, viewer"
							class="rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
						/>
					</div>

					<!-- Users -->
					<div class="flex flex-col gap-1">
						<label for="ws-users" class="text-sm font-medium text-text-primary">
							Users
						</label>
						<input
							id="ws-users"
							type="text"
							bind:value={formUsers}
							placeholder="Comma-separated, e.g. alice, bob"
							class="rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
						/>
					</div>

					<!-- Buttons -->
					<div class="flex items-center justify-end gap-2 pt-2">
						<button
							type="button"
							onclick={closeModal}
							class="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover"
						>
							Cancel
						</button>
						<button
							type="submit"
							disabled={saving || !formName.trim()}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
						>
							{#if saving}
								<Loader2 size={14} class="animate-spin" />
							{/if}
							{editingWorkspace ? 'Save Changes' : 'Create Workspace'}
						</button>
					</div>
				</form>
			</div>
		</div>
	{/if}

	<!-- Content -->
	{#if loading}
		<div class="flex flex-1 items-center justify-center">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if workspaces.length === 0}
		<!-- Empty state -->
		<div class="flex min-h-0 flex-1 flex-col items-center justify-center gap-3">
			<span class="text-text-secondary/40">
				<Folder size={48} strokeWidth={1} />
			</span>
			<h2 class="text-base font-semibold text-text-primary">No workspaces yet</h2>
			<p class="text-sm text-text-secondary">Create a workspace to organize your resources.</p>
			<button
				type="button"
				onclick={openCreateModal}
				class="mt-2 inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Create Workspace
			</button>
		</div>
	{:else}
		<!-- Workspace card grid -->
		<div class="min-h-0 flex-1 overflow-auto">
			<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
				{#each workspaces as workspace}
					<div
						class="group relative rounded-lg border border-border bg-surface transition-all hover:border-border/80 hover:shadow-md"
					>
						<!-- Colored accent bar -->
						<div
							class="h-1.5 rounded-t-lg"
							style="background-color: {workspace.color}"
						></div>

						<!-- Card body -->
						<div class="p-4">
							<!-- Header row: icon + name + color dot -->
							<div class="mb-2 flex items-center gap-2">
								<div
									class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
									style="background-color: {workspace.color}20"
								>
									<Folder size={16} style="color: {workspace.color}" />
								</div>
								<div class="min-w-0 flex-1">
									<div class="flex items-center gap-2">
										<h3 class="truncate text-sm font-semibold text-text-primary">
											{workspace.name}
										</h3>
										<span
											class="h-4 w-4 shrink-0 rounded-full"
											style="background-color: {workspace.color}"
										></span>
									</div>
								</div>
							</div>

							<!-- Description -->
							<p class="mb-3 line-clamp-2 text-xs text-text-secondary">
								{workspace.description || 'No description'}
							</p>

							<!-- Metadata chips -->
							<div class="flex items-center gap-3 text-xs text-text-secondary/60">
								<span class="inline-flex items-center gap-1">
									<Shield size={12} />
									{workspace.roles.length} {workspace.roles.length === 1 ? 'role' : 'roles'}
								</span>
								<span class="inline-flex items-center gap-1">
									<Users size={12} />
									{workspace.users.length} {workspace.users.length === 1 ? 'user' : 'users'}
								</span>
							</div>
						</div>

						<!-- Card actions -->
						<div class="flex items-center justify-end gap-1 border-t border-border px-3 py-2">
							{#if confirmingDeleteId === workspace.id}
								<div class="flex items-center gap-1.5">
									<span class="text-xs text-danger">Delete?</span>
									<button
										type="button"
										onclick={() => confirmAndDelete(workspace.id)}
										class="rounded px-1.5 py-0.5 text-xs font-medium text-danger hover:bg-danger/10"
									>
										Yes
									</button>
									<button
										type="button"
										onclick={cancelDeleteConfirm}
										class="rounded px-1.5 py-0.5 text-xs text-text-secondary hover:bg-surface-hover"
									>
										No
									</button>
								</div>
							{:else}
								<button
									type="button"
									onclick={() => openEditModal(workspace)}
									class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
									title="Edit"
								>
									<Pencil size={14} />
								</button>
								<button
									type="button"
									onclick={() => startDelete(workspace.id)}
									class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
									title="Delete"
								>
									<Trash2 size={14} />
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
