<!--
  ExportManager.svelte - Export template and history management.

  Lists export history with download/delete actions, and provides
  a form to create and delete export templates with column mapping.

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
		Download,
		FileDown,
		Settings2
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface ExportRecord {
		id: string;
		title: string;
		format: string;
		status: string;
		file_size: number | null;
		row_count: number | null;
		error: string | null;
		created_at: string | null;
	}

	interface ExportTemplate {
		id: string;
		name: string;
		format: string;
		column_mapping: Record<string, string>;
		header_text: string | null;
		footer_text: string | null;
		is_system: boolean;
		created_at: string | null;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let exports = $state<ExportRecord[]>([]);
	let templates = $state<ExportTemplate[]>([]);
	let loadingExports = $state(true);
	let loadingTemplates = $state(true);
	let error = $state('');

	// Template form state
	let showTemplateForm = $state(false);
	let savingTemplate = $state(false);
	let templateForm = $state({
		name: '',
		format: 'csv' as string,
		header_text: '',
		footer_text: '',
		column_entries: [{ key: '', value: '' }] as Array<{ key: string; value: string }>
	});

	// Active tab
	let activeTab = $state<'history' | 'templates'>('history');

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadExports() {
		loadingExports = true;
		try {
			exports = await apiJson<ExportRecord[]>('/exports');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load exports';
		} finally {
			loadingExports = false;
		}
	}

	async function loadTemplates() {
		loadingTemplates = true;
		try {
			templates = await apiJson<ExportTemplate[]>('/exports/templates');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load templates';
		} finally {
			loadingTemplates = false;
		}
	}

	$effect(() => {
		loadExports();
		loadTemplates();
	});

	// -----------------------------------------------------------------------
	// Export actions
	// -----------------------------------------------------------------------

	async function deleteExport(id: string) {
		error = '';
		try {
			await apiFetch(`/exports/${id}`, { method: 'DELETE' });
			await loadExports();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete export';
		}
	}

	// -----------------------------------------------------------------------
	// Template actions
	// -----------------------------------------------------------------------

	function openTemplateForm() {
		templateForm = {
			name: '',
			format: 'csv',
			header_text: '',
			footer_text: '',
			column_entries: [{ key: '', value: '' }]
		};
		showTemplateForm = true;
	}

	function cancelTemplateForm() {
		showTemplateForm = false;
	}

	function addColumnEntry() {
		templateForm.column_entries = [...templateForm.column_entries, { key: '', value: '' }];
	}

	function removeColumnEntry(index: number) {
		templateForm.column_entries = templateForm.column_entries.filter((_, i) => i !== index);
	}

	async function submitTemplate() {
		savingTemplate = true;
		error = '';

		const columnMapping: Record<string, string> = {};
		for (const entry of templateForm.column_entries) {
			if (entry.key.trim()) {
				columnMapping[entry.key.trim()] = entry.value.trim();
			}
		}

		const payload = {
			name: templateForm.name,
			format: templateForm.format,
			column_mapping: columnMapping,
			header_text: templateForm.header_text || null,
			footer_text: templateForm.footer_text || null
		};

		try {
			await apiJson('/exports/templates', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			showTemplateForm = false;
			await loadTemplates();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create template';
		} finally {
			savingTemplate = false;
		}
	}

	async function deleteTemplate(id: string) {
		error = '';
		try {
			await apiFetch(`/exports/templates/${id}`, { method: 'DELETE' });
			await loadTemplates();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete template';
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

	function formatBytes(bytes: number | null): string {
		if (bytes == null || bytes === 0) return '--';
		const units = ['B', 'KB', 'MB', 'GB'];
		let i = 0;
		let size = bytes;
		while (size >= 1024 && i < units.length - 1) {
			size /= 1024;
			i++;
		}
		return `${i === 0 ? size : size.toFixed(1)} ${units[i]}`;
	}

	const formatBadge: Record<string, string> = {
		csv: 'bg-success/10 text-success',
		json: 'bg-accent/10 text-accent',
		pdf: 'bg-danger/10 text-danger'
	};

	const statusBadge: Record<string, string> = {
		pending: 'bg-surface-secondary text-text-secondary',
		generating: 'bg-accent/10 text-accent',
		completed: 'bg-success/10 text-success',
		failed: 'bg-danger/10 text-danger'
	};
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Exports</h1>
			<p class="text-sm text-text-secondary">Manage export templates and view export history</p>
		</div>
	</div>

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
			onclick={() => (activeTab = 'history')}
			class="px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'history'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			Export History
		</button>
		<button
			type="button"
			onclick={() => (activeTab = 'templates')}
			class="px-4 py-2 text-sm font-medium transition-colors
				{activeTab === 'templates'
				? 'border-b-2 border-accent text-accent'
				: 'text-text-secondary hover:text-text-primary'}"
		>
			Templates
		</button>
	</div>

	<!-- ================================================================= -->
	<!-- Export History Tab                                                  -->
	<!-- ================================================================= -->
	{#if activeTab === 'history'}
		{#if loadingExports}
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
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Title</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Format</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Status</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Created</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Size</th>
								<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each exports as exp, i}
								<tr
									class="border-b border-border last:border-b-0 {i % 2 === 1
										? 'bg-surface-secondary/50'
										: ''}"
								>
									<td class="px-4 py-2 text-text-secondary">
										<FileDown size={14} />
									</td>
									<td class="px-4 py-2 font-medium text-text-primary">{exp.title}</td>
									<td class="px-4 py-2">
										<span
											class="rounded px-1.5 py-0.5 text-xs font-medium uppercase {formatBadge[
												exp.format
											] ?? ''}"
										>
											{exp.format}
										</span>
									</td>
									<td class="px-4 py-2">
										<span
											class="rounded-full px-2 py-0.5 text-xs font-medium capitalize {statusBadge[
												exp.status
											] ?? statusBadge.pending}"
										>
											{exp.status}
										</span>
									</td>
									<td class="px-4 py-2 text-xs text-text-secondary">
										{formatDate(exp.created_at)}
									</td>
									<td class="px-4 py-2 text-xs text-text-secondary">
										{formatBytes(exp.file_size)}
									</td>
									<td class="px-4 py-2">
										<div class="flex items-center gap-1">
											{#if exp.status === 'completed'}
												<a
													href="/api/exports/{exp.id}/download"
													class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent"
													title="Download"
												>
													<Download size={14} />
												</a>
											{/if}
											<button
												type="button"
												onclick={() => deleteExport(exp.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										</div>
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="7" class="px-4 py-8 text-center text-sm text-text-secondary">
										No exports yet. Exports created via the assistant will appear here.
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

	<!-- ================================================================= -->
	<!-- Templates Tab                                                      -->
	<!-- ================================================================= -->
	{:else}
		<!-- New template button -->
		<div class="flex justify-end">
			<button
				type="button"
				onclick={openTemplateForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				New Template
			</button>
		</div>

		<!-- Template creation form -->
		{#if showTemplateForm}
			<div class="rounded-lg border border-border bg-surface p-4">
				<div class="mb-3 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-text-primary">Create Template</h3>
					<button
						type="button"
						onclick={cancelTemplateForm}
						class="text-text-secondary hover:text-text-primary"
					>
						<X size={16} />
					</button>
				</div>

				<form
					onsubmit={(e) => {
						e.preventDefault();
						submitTemplate();
					}}
					class="flex flex-col gap-3"
				>
					<div class="grid grid-cols-2 gap-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Name</span>
							<input
								type="text"
								bind:value={templateForm.name}
								required
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Format</span>
							<select
								bind:value={templateForm.format}
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							>
								<option value="csv">CSV</option>
								<option value="json">JSON</option>
								<option value="pdf">PDF</option>
							</select>
						</label>
					</div>

					<div class="grid grid-cols-2 gap-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Header Text</span>
							<input
								type="text"
								bind:value={templateForm.header_text}
								placeholder="Optional header for the export"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Footer Text</span>
							<input
								type="text"
								bind:value={templateForm.footer_text}
								placeholder="Optional footer for the export"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>
					</div>

					<!-- Column mapping editor -->
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between">
							<span class="text-xs font-medium text-text-secondary">Column Mapping</span>
							<button
								type="button"
								onclick={addColumnEntry}
								class="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-hover"
							>
								<Plus size={12} />
								Add Column
							</button>
						</div>

						{#each templateForm.column_entries as entry, idx}
							<div class="flex items-center gap-2">
								<input
									type="text"
									bind:value={entry.key}
									placeholder="Source field"
									class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
								/>
								<span class="text-xs text-text-secondary">-></span>
								<input
									type="text"
									bind:value={entry.value}
									placeholder="Display name"
									class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
								/>
								{#if templateForm.column_entries.length > 1}
									<button
										type="button"
										onclick={() => removeColumnEntry(idx)}
										class="rounded p-1 text-text-secondary hover:bg-danger/10 hover:text-danger"
									>
										<X size={14} />
									</button>
								{/if}
							</div>
						{/each}
					</div>

					<div class="flex justify-end gap-2 pt-1">
						<button
							type="button"
							onclick={cancelTemplateForm}
							class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
						>
							Cancel
						</button>
						<button
							type="submit"
							disabled={savingTemplate}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if savingTemplate}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Save size={14} />
							{/if}
							Create Template
						</button>
					</div>
				</form>
			</div>
		{/if}

		<!-- Templates table -->
		{#if loadingTemplates}
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
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Format</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Columns</th>
								<th class="px-4 py-2 text-xs font-medium text-text-secondary">Created</th>
								<th class="w-16 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each templates as tmpl, i}
								<tr
									class="border-b border-border last:border-b-0 {i % 2 === 1
										? 'bg-surface-secondary/50'
										: ''}"
								>
									<td class="px-4 py-2 text-text-secondary">
										<Settings2 size={14} />
									</td>
									<td class="px-4 py-2 font-medium text-text-primary">
										{tmpl.name}
										{#if tmpl.is_system}
											<span
												class="ml-1.5 rounded bg-surface-secondary px-1.5 py-0.5 text-xs text-text-secondary"
											>
												system
											</span>
										{/if}
									</td>
									<td class="px-4 py-2">
										<span
											class="rounded px-1.5 py-0.5 text-xs font-medium uppercase {formatBadge[
												tmpl.format
											] ?? ''}"
										>
											{tmpl.format}
										</span>
									</td>
									<td class="px-4 py-2 text-xs text-text-secondary">
										{Object.keys(tmpl.column_mapping).length} columns
									</td>
									<td class="px-4 py-2 text-xs text-text-secondary">
										{formatDate(tmpl.created_at)}
									</td>
									<td class="px-4 py-2">
										{#if !tmpl.is_system}
											<button
												type="button"
												onclick={() => deleteTemplate(tmpl.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										{/if}
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="6" class="px-4 py-8 text-center text-sm text-text-secondary">
										No templates yet. Create one to define reusable export formats.
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
