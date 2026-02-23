<!--
  SkillManager.svelte - CRUD interface for agent skills.

  Lists skills in a table with create/edit modal, active toggle, tags, and
  delete with confirmation. Follows the same patterns as RoleManager and
  CatalogManager.

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
		Sparkles,
		Tag,
		ToggleLeft,
		ToggleRight
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface SkillRecord {
		id: string;
		name: string;
		description: string;
		content: string;
		tags: string[];
		active: boolean;
		created_at: string | null;
		updated_at: string | null;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let skills = $state<SkillRecord[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingSkill = $state<SkillRecord | null>(null);
	let saving = $state(false);
	let formData = $state({
		name: '',
		description: '',
		content: '',
		tags: '',
		active: true
	});

	// Delete confirmation
	let confirmingDeleteId = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadSkills() {
		loading = true;
		error = '';
		try {
			skills = await apiJson<SkillRecord[]>('/admin/skills');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load skills';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadSkills();
	});

	// -----------------------------------------------------------------------
	// Form actions
	// -----------------------------------------------------------------------

	function openCreateForm() {
		editingSkill = null;
		formData = {
			name: '',
			description: '',
			content: '',
			tags: '',
			active: true
		};
		showForm = true;
	}

	function openEditForm(skill: SkillRecord) {
		editingSkill = skill;
		formData = {
			name: skill.name,
			description: skill.description,
			content: skill.content,
			tags: skill.tags.join(', '),
			active: skill.active
		};
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editingSkill = null;
	}

	async function submitForm() {
		saving = true;
		error = '';

		const payload = {
			name: formData.name,
			description: formData.description,
			content: formData.content,
			tags: formData.tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean),
			active: formData.active
		};

		try {
			if (editingSkill) {
				await apiJson(`/admin/skills/${editingSkill.id}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/admin/skills', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			showForm = false;
			editingSkill = null;
			await loadSkills();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save skill';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Delete
	// -----------------------------------------------------------------------

	function startDelete(id: string) {
		confirmingDeleteId = id;
	}

	function cancelDeleteConfirm() {
		confirmingDeleteId = null;
	}

	async function confirmAndDelete(id: string) {
		confirmingDeleteId = null;
		error = '';
		try {
			await apiFetch(`/admin/skills/${id}`, { method: 'DELETE' });
			await loadSkills();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete skill';
		}
	}

	// -----------------------------------------------------------------------
	// Toggle active
	// -----------------------------------------------------------------------

	async function toggleActive(skill: SkillRecord) {
		error = '';
		try {
			await apiJson(`/admin/skills/${skill.id}`, {
				method: 'PUT',
				body: JSON.stringify({ active: !skill.active })
			});
			await loadSkills();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to toggle skill';
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
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Skills Management</h1>
			<p class="text-sm text-text-secondary">
				Create and manage agent skills, prompt snippets, and reusable instructions
			</p>
		</div>
		<button
			type="button"
			onclick={openCreateForm}
			class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			<Plus size={16} />
			New Skill
		</button>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Create/edit form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">
					{editingSkill ? `Edit Skill: ${editingSkill.name}` : 'Create Skill'}
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
						<span class="text-xs font-medium text-text-secondary">Name</span>
						<input
							type="text"
							bind:value={formData.name}
							required
							placeholder="e.g. summarize-ticket"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
						<input
							type="text"
							bind:value={formData.tags}
							placeholder="e.g. support, triage"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Description</span>
					<input
						type="text"
						bind:value={formData.description}
						placeholder="Brief description of what this skill does"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Content</span>
					<textarea
						bind:value={formData.content}
						rows={8}
						placeholder="Skill instructions, prompt content, or code..."
						class="rounded-md border border-border bg-surface px-3 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-accent"
					></textarea>
				</label>

				<label class="flex items-center gap-2">
					<input
						type="checkbox"
						bind:checked={formData.active}
						class="accent-accent"
					/>
					<span class="text-sm text-text-primary">Active</span>
				</label>

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
						{editingSkill ? 'Update Skill' : 'Create Skill'}
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- Skills table -->
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
							<th class="w-8 px-4 py-2"></th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Name</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Description</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Tags</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Active</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Updated</th>
							<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each skills as skill, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2 text-text-secondary">
									<Sparkles size={14} />
								</td>
								<td class="px-4 py-2 font-medium text-text-primary">
									<span class="font-mono text-xs">{skill.name}</span>
								</td>
								<td class="max-w-xs truncate px-4 py-2 text-text-secondary">
									{skill.description || '--'}
								</td>
								<td class="px-4 py-2">
									{#if skill.tags.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each skill.tags as tag}
												<span
													class="inline-flex items-center gap-0.5 rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
												>
													<Tag size={10} />
													{tag}
												</span>
											{/each}
										</div>
									{:else}
										<span class="text-xs text-text-secondary">--</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									<button
										type="button"
										onclick={() => toggleActive(skill)}
										class="text-text-secondary transition-colors hover:text-text-primary"
										title={skill.active ? 'Deactivate' : 'Activate'}
									>
										{#if skill.active}
											<ToggleRight size={20} class="text-success" />
										{:else}
											<ToggleLeft size={20} />
										{/if}
									</button>
								</td>
								<td class="px-4 py-2 text-xs text-text-secondary">
									{formatDate(skill.updated_at)}
								</td>
								<td class="px-4 py-2">
									{#if confirmingDeleteId === skill.id}
										<div class="flex items-center gap-1.5">
											<span class="text-xs text-danger">Delete?</span>
											<button
												type="button"
												onclick={() => confirmAndDelete(skill.id)}
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
										<div class="flex items-center gap-1">
											<button
												type="button"
												onclick={() => openEditForm(skill)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent"
												title="Edit"
											>
												<Pencil size={14} />
											</button>
											<button
												type="button"
												onclick={() => startDelete(skill.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										</div>
									{/if}
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="7" class="px-4 py-8 text-center text-sm text-text-secondary">
									No skills found. Create one to get started.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
