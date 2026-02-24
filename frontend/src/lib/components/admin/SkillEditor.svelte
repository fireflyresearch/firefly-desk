<!--
  SkillEditor.svelte - Structured skill editing modal with live preview.

  Two-panel layout: left panel for structured/raw editing of steps,
  guidelines, endpoint/document references; right panel for live
  markdown preview. Supports both structured and raw editing modes.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		Save,
		Loader2,
		Plus,
		ChevronUp,
		ChevronDown,
		Eye,
		EyeOff,
		Code,
		FileText,
		Zap,
		BookOpen,
		AlertTriangle
	} from 'lucide-svelte';
	import { untrack } from 'svelte';
	import { apiJson } from '$lib/services/api.js';

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
	}

	interface StepEntry {
		description: string;
		endpointId: string;
	}

	interface AvailableEndpoint {
		id: string;
		name: string;
		system_id: string;
		method: string;
		path: string;
	}

	interface SystemInfo {
		id: string;
		name: string;
		agent_enabled: boolean;
	}

	interface AvailableDocument {
		id: string;
		title: string;
		type: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let {
		editingSkill = null,
		onClose,
		onSaved
	}: {
		editingSkill?: SkillRecord | null;
		onClose: () => void;
		onSaved: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// Initial values (captured once at mount)
	// -----------------------------------------------------------------------

	const _init = untrack(() => editingSkill);
	const isEditMode = _init !== null;

	// -----------------------------------------------------------------------
	// State - basic fields
	// -----------------------------------------------------------------------

	let name = $state(_init?.name ?? '');
	let description = $state(_init?.description ?? '');
	let tags = $state(_init?.tags?.join(', ') ?? '');
	let active = $state(_init?.active ?? true);
	let saving = $state(false);
	let error = $state('');

	// -----------------------------------------------------------------------
	// State - editing mode
	// -----------------------------------------------------------------------

	let useStructuredMode = $state(true);
	let rawContent = $state(_init?.content ?? '');
	let showPreview = $state(true);

	// -----------------------------------------------------------------------
	// State - structured fields
	// -----------------------------------------------------------------------

	let steps = $state<StepEntry[]>([{ description: '', endpointId: '' }]);
	let guidelines = $state<string[]>(['']);
	let referencedEndpoints = $state<string[]>([]);
	let referencedDocuments = $state<string[]>([]);

	// -----------------------------------------------------------------------
	// State - reference data
	// -----------------------------------------------------------------------

	let systems = $state<SystemInfo[]>([]);
	let availableEndpoints = $state<AvailableEndpoint[]>([]);
	let availableDocuments = $state<AvailableDocument[]>([]);

	// -----------------------------------------------------------------------
	// Content parsing (edit mode)
	// -----------------------------------------------------------------------

	function parseContent(content: string): boolean {
		const stepsMatch = content.match(/## Steps\n([\s\S]*?)(?=\n## |$)/);
		const guidelinesMatch = content.match(/## Guidelines\n([\s\S]*?)(?=\n## |$)/);
		const endpointsMatch = content.match(/## Referenced Endpoints\n([\s\S]*?)(?=\n## |$)/);
		const docsMatch = content.match(/## Referenced Documents\n([\s\S]*?)(?=\n## |$)/);

		if (!stepsMatch && !guidelinesMatch) return false;

		if (stepsMatch) {
			const lines = stepsMatch[1]
				.trim()
				.split('\n')
				.filter((l) => l.match(/^\d+\./));
			steps = lines.map((l) => {
				const text = l.replace(/^\d+\.\s*/, '').trim();
				const epMatch = text.match(/\[endpoint:([^\]]+)\]/);
				return {
					description: text.replace(/\s*\[endpoint:[^\]]+\]/, '').trim(),
					endpointId: epMatch?.[1] || ''
				};
			});
			if (steps.length === 0) steps = [{ description: '', endpointId: '' }];
		}

		if (guidelinesMatch) {
			guidelines = guidelinesMatch[1]
				.trim()
				.split('\n')
				.filter((l) => l.startsWith('- '))
				.map((l) => l.replace(/^- /, '').trim());
			if (guidelines.length === 0) guidelines = [''];
		}

		if (endpointsMatch) {
			referencedEndpoints = endpointsMatch[1]
				.trim()
				.split('\n')
				.filter((l) => l.startsWith('- '))
				.map((l) => l.replace(/^- /, '').trim());
		}

		if (docsMatch) {
			referencedDocuments = docsMatch[1]
				.trim()
				.split('\n')
				.filter((l) => l.startsWith('- '))
				.map((l) => l.replace(/^- /, '').trim());
		}

		return true;
	}

	// Initialize structured fields from existing content
	if (isEditMode && _init?.content) {
		const parsed = parseContent(_init.content);
		if (!parsed) {
			useStructuredMode = false;
		}
	}

	// -----------------------------------------------------------------------
	// Content generation
	// -----------------------------------------------------------------------

	function generateContent(): string {
		if (!useStructuredMode) return rawContent;

		let content = '';

		const validSteps = steps.filter((s) => s.description.trim());
		if (validSteps.length > 0) {
			content += '## Steps\n';
			validSteps.forEach((s, i) => {
				content += `${i + 1}. ${s.description}`;
				if (s.endpointId) content += ` [endpoint:${s.endpointId}]`;
				content += '\n';
			});
			content += '\n';
		}

		const validGuidelines = guidelines.filter((g) => g.trim());
		if (validGuidelines.length > 0) {
			content += '## Guidelines\n';
			validGuidelines.forEach((g) => {
				content += `- ${g}\n`;
			});
			content += '\n';
		}

		if (referencedEndpoints.length > 0) {
			content += '## Referenced Endpoints\n';
			referencedEndpoints.forEach((id) => {
				content += `- ${id}\n`;
			});
			content += '\n';
		}

		if (referencedDocuments.length > 0) {
			content += '## Referenced Documents\n';
			referencedDocuments.forEach((id) => {
				content += `- ${id}\n`;
			});
			content += '\n';
		}

		return content.trim();
	}

	let previewContent = $derived(useStructuredMode ? generateContent() : rawContent);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadReferenceData() {
		try {
			const loadedSystems = await apiJson<SystemInfo[]>('/catalog/systems');
			systems = loadedSystems;
			const allEndpoints: AvailableEndpoint[] = [];
			for (const sys of loadedSystems) {
				try {
					const eps = await apiJson<AvailableEndpoint[]>(
						`/catalog/systems/${sys.id}/endpoints`
					);
					allEndpoints.push(...eps);
				} catch {
					/* skip system on error */
				}
			}
			availableEndpoints = allEndpoints;
		} catch {
			/* non-fatal */
		}

		try {
			availableDocuments = await apiJson<AvailableDocument[]>('/knowledge/documents');
		} catch {
			/* non-fatal */
		}
	}

	$effect(() => {
		loadReferenceData();
	});

	// -----------------------------------------------------------------------
	// Step management
	// -----------------------------------------------------------------------

	function addStep() {
		steps = [...steps, { description: '', endpointId: '' }];
	}

	function removeStep(index: number) {
		if (steps.length <= 1) return;
		steps = steps.filter((_, i) => i !== index);
	}

	function moveStep(index: number, direction: -1 | 1) {
		const target = index + direction;
		if (target < 0 || target >= steps.length) return;
		const updated = [...steps];
		[updated[index], updated[target]] = [updated[target], updated[index]];
		steps = updated;
	}

	// -----------------------------------------------------------------------
	// Guideline management
	// -----------------------------------------------------------------------

	function addGuideline() {
		guidelines = [...guidelines, ''];
	}

	function removeGuideline(index: number) {
		if (guidelines.length <= 1) return;
		guidelines = guidelines.filter((_, i) => i !== index);
	}

	function updateGuideline(index: number, value: string) {
		guidelines = guidelines.map((g, i) => (i === index ? value : g));
	}

	// -----------------------------------------------------------------------
	// Reference management
	// -----------------------------------------------------------------------

	let endpointSelectValue = $state('');
	let documentSelectValue = $state('');

	function addReferencedEndpoint() {
		if (!endpointSelectValue || referencedEndpoints.includes(endpointSelectValue)) return;
		referencedEndpoints = [...referencedEndpoints, endpointSelectValue];
		endpointSelectValue = '';
	}

	function removeReferencedEndpoint(id: string) {
		referencedEndpoints = referencedEndpoints.filter((e) => e !== id);
	}

	function addReferencedDocument() {
		if (!documentSelectValue || referencedDocuments.includes(documentSelectValue)) return;
		referencedDocuments = [...referencedDocuments, documentSelectValue];
		documentSelectValue = '';
	}

	function removeReferencedDocument(id: string) {
		referencedDocuments = referencedDocuments.filter((d) => d !== id);
	}

	// -----------------------------------------------------------------------
	// Endpoint display helpers
	// -----------------------------------------------------------------------

	function endpointLabel(id: string): string {
		const ep = availableEndpoints.find((e) => e.id === id);
		return ep ? `${ep.method} ${ep.path}` : id;
	}

	function documentLabel(id: string): string {
		const doc = availableDocuments.find((d) => d.id === id);
		return doc ? doc.title : id;
	}

	// -----------------------------------------------------------------------
	// Mode toggle
	// -----------------------------------------------------------------------

	function switchToRawMode() {
		rawContent = generateContent();
		useStructuredMode = false;
	}

	function switchToStructuredMode() {
		const parsed = parseContent(rawContent);
		if (!parsed) {
			error = 'Could not parse raw content into structured format. Check the markdown structure.';
			return;
		}
		error = '';
		useStructuredMode = true;
	}

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	const isValid = $derived(name.trim() !== '');

	// -----------------------------------------------------------------------
	// Endpoint warnings
	// -----------------------------------------------------------------------

	let endpointWarnings = $derived.by(() => {
		const warnings: string[] = [];
		const allEndpointIds = new Set(availableEndpoints.map((e) => e.id));
		const disabledSystemIds = new Set(
			systems.filter((s) => !s.agent_enabled).map((s) => s.id)
		);

		// Check referenced endpoints
		for (const epId of referencedEndpoints) {
			if (!allEndpointIds.has(epId)) {
				warnings.push(`Endpoint "${epId}" not found in catalog`);
			} else {
				const ep = availableEndpoints.find((e) => e.id === epId);
				if (ep && disabledSystemIds.has(ep.system_id)) {
					const sys = systems.find((s) => s.id === ep.system_id);
					warnings.push(
						`Endpoint "${epId}" belongs to "${sys?.name || ep.system_id}" which has agent access disabled`
					);
				}
			}
		}

		// Check step endpoints
		for (const step of steps) {
			if (step.endpointId && !allEndpointIds.has(step.endpointId)) {
				warnings.push(`Step endpoint "${step.endpointId}" not found in catalog`);
			} else if (step.endpointId) {
				const ep = availableEndpoints.find((e) => e.id === step.endpointId);
				if (ep && disabledSystemIds.has(ep.system_id)) {
					const sys = systems.find((s) => s.id === ep.system_id);
					warnings.push(
						`Step endpoint "${step.endpointId}" belongs to "${sys?.name || ep.system_id}" which has agent access disabled`
					);
				}
			}
		}

		return warnings;
	});

	// -----------------------------------------------------------------------
	// Submit
	// -----------------------------------------------------------------------

	async function submit() {
		if (!isValid) return;

		saving = true;
		error = '';

		const payload = {
			name: name.trim(),
			description: description.trim(),
			content: generateContent(),
			tags: tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean),
			active
		};

		try {
			if (isEditMode) {
				await apiJson(`/admin/skills/${_init!.id}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/admin/skills', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save skill';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Event handlers
	// -----------------------------------------------------------------------

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Modal backdrop -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
	role="presentation"
	onclick={handleBackdropClick}
>
	<!-- Modal content -->
	<div class="mx-4 flex max-h-[90vh] w-full max-w-5xl flex-col rounded-xl bg-surface shadow-2xl">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-border px-6 py-4">
			<div class="flex items-center gap-2">
				<Zap size={18} class="text-accent" />
				<h2 class="text-base font-semibold text-text-primary">
					{isEditMode ? 'Edit Skill' : 'New Skill'}
				</h2>
			</div>
			<div class="flex items-center gap-2">
				<!-- Mode toggle -->
				<div class="flex items-center gap-1 rounded-md border border-border bg-surface-secondary p-0.5">
					<button
						type="button"
						onclick={() => {
							if (!useStructuredMode) switchToStructuredMode();
						}}
						class="inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors
							{useStructuredMode
							? 'bg-surface text-text-primary shadow-sm'
							: 'text-text-secondary hover:text-text-primary'}"
					>
						<FileText size={12} />
						Structured
					</button>
					<button
						type="button"
						onclick={() => {
							if (useStructuredMode) switchToRawMode();
						}}
						class="inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors
							{!useStructuredMode
							? 'bg-surface text-text-primary shadow-sm'
							: 'text-text-secondary hover:text-text-primary'}"
					>
						<Code size={12} />
						Raw
					</button>
				</div>

				<!-- Preview toggle -->
				<button
					type="button"
					onclick={() => (showPreview = !showPreview)}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
					title={showPreview ? 'Hide preview' : 'Show preview'}
				>
					{#if showPreview}
						<EyeOff size={12} />
					{:else}
						<Eye size={12} />
					{/if}
					Preview
				</button>

				<button
					type="button"
					onclick={onClose}
					class="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={18} />
				</button>
			</div>
		</div>

		<!-- Error banner -->
		{#if error}
			<div
				class="mx-6 mt-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
			>
				<AlertTriangle size={16} class="mt-0.5 shrink-0" />
				<span>{error}</span>
			</div>
		{/if}

		<!-- Body: two-panel layout -->
		<div class="flex min-h-0 flex-1">
			<!-- Left panel: editor -->
			<div
				class="flex-1 overflow-y-auto border-r border-border px-6 py-5"
				class:border-r-0={!showPreview}
			>
				<!-- Basic fields -->
				<div class="flex flex-col gap-3">
					<div class="grid grid-cols-2 gap-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary"
								>Name <span class="text-danger">*</span></span
							>
							<input
								type="text"
								bind:value={name}
								required
								placeholder="e.g. summarize-ticket"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary"
								>Tags (comma-separated)</span
							>
							<input
								type="text"
								bind:value={tags}
								placeholder="e.g. support, triage"
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>
					</div>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Description</span>
						<input
							type="text"
							bind:value={description}
							placeholder="Brief description of what this skill does"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<label class="flex items-center gap-2">
						<input type="checkbox" bind:checked={active} class="accent-accent" />
						<span class="text-sm text-text-primary">Active</span>
					</label>
				</div>

				<hr class="my-4 border-border" />

				<!-- Structured mode -->
				{#if useStructuredMode}
					<!-- Steps section -->
					<div class="flex flex-col gap-3">
						<div class="flex items-center justify-between">
							<h3
								class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary"
							>
								<Zap size={12} />
								Steps
							</h3>
							<button
								type="button"
								onclick={addStep}
								class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
							>
								<Plus size={12} />
								Add Step
							</button>
						</div>

						{#each steps as step, i}
							<div
								class="flex items-start gap-2 rounded-md border border-border bg-surface-secondary/30 p-3"
							>
								<span
									class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/10 text-xs font-semibold text-accent"
								>
									{i + 1}
								</span>
								<div class="flex min-w-0 flex-1 flex-col gap-2">
									<textarea
										bind:value={step.description}
										rows={2}
										placeholder="Describe this step..."
										class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
									></textarea>
									{#if availableEndpoints.length > 0}
										<select
											bind:value={step.endpointId}
											class="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
										>
											<option value="">No endpoint</option>
											{#each availableEndpoints as ep}
												<option value={ep.id}
													>{ep.method} {ep.path} ({ep.name})</option
												>
											{/each}
										</select>
									{/if}
								</div>
								<div class="flex shrink-0 flex-col gap-0.5">
									<button
										type="button"
										onclick={() => moveStep(i, -1)}
										disabled={i === 0}
										class="rounded p-0.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-30"
										title="Move up"
									>
										<ChevronUp size={14} />
									</button>
									<button
										type="button"
										onclick={() => moveStep(i, 1)}
										disabled={i === steps.length - 1}
										class="rounded p-0.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-30"
										title="Move down"
									>
										<ChevronDown size={14} />
									</button>
									<button
										type="button"
										onclick={() => removeStep(i)}
										disabled={steps.length <= 1}
										class="rounded p-0.5 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger disabled:opacity-30"
										title="Remove step"
									>
										<X size={14} />
									</button>
								</div>
							</div>
						{/each}
					</div>

					<hr class="my-4 border-border" />

					<!-- Guidelines section -->
					<div class="flex flex-col gap-3">
						<div class="flex items-center justify-between">
							<h3
								class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary"
							>
								<BookOpen size={12} />
								Guidelines
							</h3>
							<button
								type="button"
								onclick={addGuideline}
								class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
							>
								<Plus size={12} />
								Add Guideline
							</button>
						</div>

						{#each guidelines as guideline, i}
							<div class="flex items-center gap-2">
								<span class="text-xs text-text-secondary">-</span>
								<input
									type="text"
									value={guideline}
									oninput={(e) =>
										updateGuideline(i, (e.target as HTMLInputElement).value)}
									placeholder="Enter guideline..."
									class="min-w-0 flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
								/>
								<button
									type="button"
									onclick={() => removeGuideline(i)}
									disabled={guidelines.length <= 1}
									class="shrink-0 rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger disabled:opacity-30"
									title="Remove guideline"
								>
									<X size={14} />
								</button>
							</div>
						{/each}
					</div>

					<hr class="my-4 border-border" />

					<!-- Referenced Endpoints section -->
					<div class="flex flex-col gap-3">
						<h3
							class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary"
						>
							<Zap size={12} />
							Referenced Endpoints
						</h3>

						{#if referencedEndpoints.length > 0}
							<div class="flex flex-wrap gap-1.5">
								{#each referencedEndpoints as epId}
									<span
										class="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent"
									>
										{endpointLabel(epId)}
										<button
											type="button"
											onclick={() => removeReferencedEndpoint(epId)}
											class="rounded-full p-0.5 transition-colors hover:bg-accent/20"
										>
											<X size={10} />
										</button>
									</span>
								{/each}
							</div>
						{/if}

						{#if availableEndpoints.length > 0}
							<div class="flex items-center gap-2">
								<select
									bind:value={endpointSelectValue}
									class="min-w-0 flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
								>
									<option value="">Select endpoint to add...</option>
									{#each availableEndpoints.filter((ep) => !referencedEndpoints.includes(ep.id)) as ep}
										<option value={ep.id}
											>{ep.method} {ep.path} ({ep.name})</option
										>
									{/each}
								</select>
								<button
									type="button"
									onclick={addReferencedEndpoint}
									disabled={!endpointSelectValue}
									class="shrink-0 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-50"
								>
									<Plus size={12} />
								</button>
							</div>
						{:else}
							<p class="text-xs text-text-secondary">
								No endpoints available. Add systems in the Catalog first.
							</p>
						{/if}
					</div>

					<hr class="my-4 border-border" />

					<!-- Referenced Documents section -->
					<div class="flex flex-col gap-3">
						<h3
							class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary"
						>
							<FileText size={12} />
							Referenced Documents
						</h3>

						{#if referencedDocuments.length > 0}
							<div class="flex flex-wrap gap-1.5">
								{#each referencedDocuments as docId}
									<span
										class="inline-flex items-center gap-1 rounded-full bg-surface-secondary px-2.5 py-1 text-xs font-medium text-text-primary"
									>
										{documentLabel(docId)}
										<button
											type="button"
											onclick={() => removeReferencedDocument(docId)}
											class="rounded-full p-0.5 transition-colors hover:bg-surface-hover"
										>
											<X size={10} />
										</button>
									</span>
								{/each}
							</div>
						{/if}

						{#if availableDocuments.length > 0}
							<div class="flex items-center gap-2">
								<select
									bind:value={documentSelectValue}
									class="min-w-0 flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
								>
									<option value="">Select document to add...</option>
									{#each availableDocuments.filter((d) => !referencedDocuments.includes(d.id)) as doc}
										<option value={doc.id}>{doc.title} ({doc.type})</option>
									{/each}
								</select>
								<button
									type="button"
									onclick={addReferencedDocument}
									disabled={!documentSelectValue}
									class="shrink-0 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-50"
								>
									<Plus size={12} />
								</button>
							</div>
						{:else}
							<p class="text-xs text-text-secondary">
								No documents available. Add documents in the Knowledge Base first.
							</p>
						{/if}
					</div>

					<!-- Endpoint warnings -->
					{#if endpointWarnings.length > 0}
						<hr class="my-4 border-border" />
						<div class="rounded-md border border-warning/30 bg-warning/5 px-3 py-2">
							<p class="mb-1 flex items-center gap-1.5 text-xs font-medium text-warning">
								<AlertTriangle size={12} />
								Endpoint Warnings
							</p>
							{#each endpointWarnings as warning}
								<p class="text-xs text-warning/80">&bull; {warning}</p>
							{/each}
						</div>
					{/if}

				{:else}
					<!-- Raw mode -->
					<div class="flex flex-col gap-2">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Content (Markdown)</span>
							<textarea
								bind:value={rawContent}
								rows={20}
								placeholder="## Steps&#10;1. First step&#10;2. Second step&#10;&#10;## Guidelines&#10;- Be concise&#10;- Use clear language"
								class="w-full rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							></textarea>
						</label>
					</div>
				{/if}
			</div>

			<!-- Right panel: live preview -->
			{#if showPreview}
				<div class="flex w-2/5 shrink-0 flex-col">
					<div
						class="flex items-center gap-1.5 border-b border-border px-4 py-2.5"
					>
						<Eye size={12} class="text-text-secondary" />
						<span class="text-xs font-medium text-text-secondary">Preview</span>
					</div>
					<div class="flex-1 overflow-y-auto px-4 py-4">
						{#if previewContent.trim()}
							<div class="prose prose-sm max-w-none">
								{#each previewContent.split('\n') as line}
									{#if line.startsWith('## ')}
										<h3
											class="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-text-secondary"
										>
											{line.replace('## ', '')}
										</h3>
									{:else if line.match(/^\d+\./)}
										<p class="ml-2 text-sm text-text-primary">{line}</p>
									{:else if line.startsWith('- ')}
										<p class="ml-2 text-sm text-text-primary">{line}</p>
									{:else if line.trim()}
										<p class="text-sm text-text-primary">{line}</p>
									{/if}
								{/each}
							</div>
						{:else}
							<div class="flex flex-col items-center justify-center py-12 text-text-secondary">
								<FileText size={24} class="mb-2 opacity-50" />
								<p class="text-xs">Content preview will appear here</p>
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-between border-t border-border px-6 py-4">
			<div class="text-xs text-text-secondary">
				{#if useStructuredMode}
					{steps.filter((s) => s.description.trim()).length} step{steps.filter((s) => s.description.trim()).length !== 1 ? 's' : ''},
					{guidelines.filter((g) => g.trim()).length} guideline{guidelines.filter((g) => g.trim()).length !== 1 ? 's' : ''}
				{:else}
					Raw editing mode
				{/if}
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					onclick={onClose}
					class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={submit}
					disabled={saving || !isValid}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Save size={14} />
					{/if}
					{isEditMode ? 'Update Skill' : 'Create Skill'}
				</button>
			</div>
		</div>
	</div>
</div>
