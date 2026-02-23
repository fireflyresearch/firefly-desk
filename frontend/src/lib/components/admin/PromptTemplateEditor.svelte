<!--
  PromptTemplateEditor.svelte - View and edit prompt templates.

  Lists all .j2 templates with their override status. Select a template
  to view its source in a monospace textarea, edit, and save overrides
  via the PUT API. Includes a "Reset to Default" action.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		FileCode,
		Save,
		Loader2,
		RotateCcw,
		CheckCircle2,
		AlertCircle
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface TemplateInfo {
		name: string;
		has_override: boolean;
	}

	interface TemplateDetail {
		name: string;
		source: string;
		has_override: boolean;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let templates = $state<TemplateInfo[]>([]);
	let loading = $state(true);
	let error = $state('');
	let successMessage = $state('');

	// Selected template
	let selectedName = $state<string | null>(null);
	let selectedDetail = $state<TemplateDetail | null>(null);
	let loadingDetail = $state(false);
	let editedSource = $state('');
	let saving = $state(false);
	let resetting = $state(false);

	// Track if content has been modified
	let isDirty = $derived(
		selectedDetail !== null && editedSource !== selectedDetail.source
	);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadTemplates() {
		loading = true;
		error = '';
		try {
			templates = await apiJson<TemplateInfo[]>('/admin/prompts/templates');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load templates';
		} finally {
			loading = false;
		}
	}

	async function selectTemplate(name: string) {
		selectedName = name;
		loadingDetail = true;
		error = '';
		successMessage = '';
		try {
			selectedDetail = await apiJson<TemplateDetail>(`/admin/prompts/templates/${name}`);
			editedSource = selectedDetail.source;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load template';
			selectedDetail = null;
		} finally {
			loadingDetail = false;
		}
	}

	$effect(() => {
		loadTemplates();
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	async function saveTemplate() {
		if (!selectedName) return;
		saving = true;
		error = '';
		successMessage = '';

		try {
			const result = await apiJson<TemplateDetail>(`/admin/prompts/templates/${selectedName}`, {
				method: 'PUT',
				body: JSON.stringify({ source: editedSource })
			});
			selectedDetail = result;
			editedSource = result.source;
			successMessage = 'Template saved successfully.';
			await loadTemplates();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save template';
		} finally {
			saving = false;
		}
	}

	async function resetToDefault() {
		if (!selectedName) return;
		if (!confirm('Reset this template to its built-in default? Your override will be removed.'))
			return;

		resetting = true;
		error = '';
		successMessage = '';

		try {
			const result = await apiJson<TemplateDetail>(
				`/admin/prompts/templates/${selectedName}/override`,
				{ method: 'DELETE' }
			);
			selectedDetail = result;
			editedSource = result.source;
			successMessage = 'Template reset to default.';
			await loadTemplates();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to reset template';
		} finally {
			resetting = false;
		}
	}
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div>
		<h1 class="text-lg font-semibold text-text-primary">Prompt Templates</h1>
		<p class="text-sm text-text-secondary">
			View and customize the Jinja2 prompt templates used by the agent
		</p>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			<div class="flex items-center gap-2">
				<AlertCircle size={14} />
				{error}
			</div>
		</div>
	{/if}

	<!-- Success banner -->
	{#if successMessage}
		<div class="rounded-md border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success">
			<div class="flex items-center gap-2">
				<CheckCircle2 size={14} />
				{successMessage}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="flex flex-1 gap-4 overflow-hidden">
			<!-- Template list -->
			<div
				class="flex w-64 shrink-0 flex-col overflow-y-auto rounded-lg border border-border bg-surface"
			>
				<div
					class="border-b border-border bg-surface-secondary px-3 py-2 text-xs font-medium text-text-secondary"
				>
					Templates ({templates.length})
				</div>
				<ul class="flex flex-col">
					{#each templates as tmpl}
						<li>
							<button
								type="button"
								onclick={() => selectTemplate(tmpl.name)}
								class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors
									{selectedName === tmpl.name
									? 'bg-accent/10 font-medium text-accent'
									: 'text-text-primary hover:bg-surface-hover'}"
							>
								<FileCode size={14} class="shrink-0" />
								<span class="truncate">{tmpl.name}</span>
								{#if tmpl.has_override}
									<span
										class="ml-auto shrink-0 rounded bg-warning/10 px-1 py-0.5 text-[10px] font-medium text-warning"
									>
										modified
									</span>
								{/if}
							</button>
						</li>
					{:else}
						<li class="px-3 py-4 text-center text-xs text-text-secondary">
							No templates found.
						</li>
					{/each}
				</ul>
			</div>

			<!-- Editor -->
			<div class="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-surface">
				{#if loadingDetail}
					<div class="flex flex-1 items-center justify-center">
						<Loader2 size={24} class="animate-spin text-text-secondary" />
					</div>
				{:else if selectedDetail}
					<!-- Editor header -->
					<div
						class="flex items-center justify-between border-b border-border bg-surface-secondary px-4 py-2"
					>
						<div class="flex items-center gap-2">
							<span class="text-sm font-medium text-text-primary">
								{selectedDetail.name}.j2
							</span>
							{#if selectedDetail.has_override}
								<span
									class="rounded bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-warning"
								>
									override active
								</span>
							{/if}
							{#if isDirty}
								<span
									class="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent"
								>
									unsaved changes
								</span>
							{/if}
						</div>
						<div class="flex items-center gap-2">
							{#if selectedDetail.has_override}
								<button
									type="button"
									onclick={resetToDefault}
									disabled={resetting}
									class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
								>
									{#if resetting}
										<Loader2 size={12} class="animate-spin" />
									{:else}
										<RotateCcw size={12} />
									{/if}
									Reset to Default
								</button>
							{/if}
							<button
								type="button"
								onclick={saveTemplate}
								disabled={saving || !isDirty}
								class="inline-flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
							>
								{#if saving}
									<Loader2 size={12} class="animate-spin" />
								{:else}
									<Save size={12} />
								{/if}
								Save Override
							</button>
						</div>
					</div>

					<!-- Textarea -->
					<textarea
						bind:value={editedSource}
						spellcheck={false}
						class="flex-1 resize-none bg-surface p-4 font-mono text-sm leading-relaxed text-text-primary outline-none"
					></textarea>
				{:else}
					<div class="flex flex-1 flex-col items-center justify-center gap-2 text-text-secondary">
						<FileCode size={32} strokeWidth={1} />
						<p class="text-sm">Select a template to view and edit</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
