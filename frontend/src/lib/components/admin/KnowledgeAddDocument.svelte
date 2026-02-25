<!--
  KnowledgeAddDocument.svelte - Multi-method document ingestion form.

  Provides five sub-tabs for adding documents to the knowledge base:
  Text input, File upload, URL import, OpenAPI import, and GitHub import.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		FileText,
		Upload,
		Globe,
		Code2,
		Github,
		Loader2,
		Save,
		X,
		Plus,
		CheckCircle2,
		AlertCircle
	} from 'lucide-svelte';
	import { apiJson, apiFetch, getToken } from '$lib/services/api.js';
	import KnowledgeGitHubImporter from './KnowledgeGitHubImporter.svelte';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		onDocumentAdded?: () => void;
	}

	let { onDocumentAdded }: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	type SubTab = 'text' | 'file' | 'url' | 'openapi' | 'github';

	interface DocumentType {
		value: string;
		label: string;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const documentTypes: DocumentType[] = [
		{ value: 'text', label: 'Plain Text' },
		{ value: 'markdown', label: 'Markdown' },
		{ value: 'html', label: 'HTML' },
		{ value: 'pdf', label: 'PDF' },
		{ value: 'code', label: 'Code' },
		{ value: 'api_spec', label: 'API Spec' },
		{ value: 'other', label: 'Other' }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let activeSubTab = $state<SubTab>('text');
	let saving = $state(false);
	let error = $state('');
	let success = $state('');

	// Text form
	let textForm = $state({
		title: '',
		type: 'text',
		content: '',
		tags: ''
	});

	// File upload
	let fileForm = $state({
		tags: ''
	});
	let selectedFiles = $state<File[]>([]);
	let dragOver = $state(false);
	let uploadResults = $state<{
		documents: { filename: string; document_id: string; status: string }[];
		errors: { filename: string; error: string }[];
	} | null>(null);

	let totalFileSize = $derived(selectedFiles.reduce((sum, f) => sum + f.size, 0));

	// URL import
	let urlForm = $state({
		url: '',
		title: '',
		tags: ''
	});
	let urlPreview = $state<{ title?: string; description?: string } | null>(null);
	let fetchingPreview = $state(false);

	// OpenAPI import
	interface OpenapiEntry {
		spec: string;
		title: string;
		preview: { endpoints: number; title?: string } | null;
	}

	let openapiEntries = $state<OpenapiEntry[]>([{ spec: '', title: '', preview: null }]);
	let openapiTags = $state('');
	let openapiImportResults = $state<
		{ title: string; success: boolean; error?: string }[] | null
	>(null);

	let validOpenapiCount = $derived(openapiEntries.filter((e) => e.spec.trim().length > 0).length);

	// -----------------------------------------------------------------------
	// Sub-tab definitions
	// -----------------------------------------------------------------------

	const subTabs: { id: SubTab; label: string; icon: typeof FileText }[] = [
		{ id: 'text', label: 'Text', icon: FileText },
		{ id: 'file', label: 'File Upload', icon: Upload },
		{ id: 'url', label: 'URL Import', icon: Globe },
		{ id: 'openapi', label: 'OpenAPI Import', icon: Code2 },
		{ id: 'github', label: 'GitHub Import', icon: Github }
	];

	// -----------------------------------------------------------------------
	// Text submission
	// -----------------------------------------------------------------------

	async function submitText() {
		saving = true;
		error = '';
		success = '';

		const payload = {
			title: textForm.title,
			type: textForm.type,
			content: textForm.content,
			tags: textForm.tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean)
		};

		try {
			await apiJson('/knowledge/documents', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			success = 'Document created successfully.';
			textForm = { title: '', type: 'text', content: '', tags: '' };
			onDocumentAdded?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create document';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// File upload
	// -----------------------------------------------------------------------

	function handleFileDrop(event: DragEvent) {
		event.preventDefault();
		dragOver = false;
		const files = event.dataTransfer?.files;
		if (files && files.length > 0) {
			selectedFiles = [...selectedFiles, ...Array.from(files)];
			uploadResults = null;
		}
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const files = input.files;
		if (files && files.length > 0) {
			selectedFiles = [...selectedFiles, ...Array.from(files)];
			uploadResults = null;
		}
		// Reset input so re-selecting the same files triggers onchange
		input.value = '';
	}

	function removeFile(index: number) {
		selectedFiles = selectedFiles.filter((_, i) => i !== index);
		if (selectedFiles.length === 0) {
			uploadResults = null;
		}
	}

	function clearFiles() {
		selectedFiles = [];
		uploadResults = null;
	}

	function formatFileSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	async function submitFiles() {
		if (selectedFiles.length === 0) return;
		saving = true;
		error = '';
		success = '';
		uploadResults = null;

		const formData = new FormData();
		for (const file of selectedFiles) {
			formData.append('files', file);
		}
		if (fileForm.tags) {
			formData.append('tags', fileForm.tags);
		}

		try {
			const headers: Record<string, string> = {};
			const token = getToken();
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}

			const response = await fetch('/api/knowledge/documents/import-files', {
				method: 'POST',
				headers,
				body: formData
			});

			if (!response.ok) {
				const body = await response.text().catch(() => '');
				throw new Error(`API ${response.status}: ${body}`);
			}

			const result = await response.json();
			uploadResults = result;

			const successCount = result.documents?.length ?? 0;
			const errorCount = result.errors?.length ?? 0;

			if (errorCount === 0) {
				success = `${successCount} file${successCount !== 1 ? 's' : ''} imported successfully.`;
			} else if (successCount === 0) {
				error = `All ${errorCount} file${errorCount !== 1 ? 's' : ''} failed to import.`;
			} else {
				success = `${successCount} file${successCount !== 1 ? 's' : ''} imported, ${errorCount} failed.`;
			}

			selectedFiles = [];
			fileForm = { tags: '' };
			onDocumentAdded?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to upload files';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// URL import
	// -----------------------------------------------------------------------

	async function submitUrl() {
		saving = true;
		error = '';
		success = '';

		const payload = {
			url: urlForm.url,
			title: urlForm.title || undefined,
			tags: urlForm.tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean)
		};

		try {
			await apiJson('/knowledge/documents/import-url', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			success = 'URL imported successfully.';
			urlForm = { url: '', title: '', tags: '' };
			urlPreview = null;
			onDocumentAdded?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to import URL';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// OpenAPI import
	// -----------------------------------------------------------------------

	function addOpenapiEntry() {
		openapiEntries = [...openapiEntries, { spec: '', title: '', preview: null }];
	}

	function removeOpenapiEntry(index: number) {
		if (openapiEntries.length <= 1) return;
		openapiEntries = openapiEntries.filter((_, i) => i !== index);
	}

	function parseOpenapiPreview(spec: string): { endpoints: number; title?: string } | null {
		if (spec.trim().length < 10) return null;
		try {
			const parsed = JSON.parse(spec);
			const paths = parsed.paths ? Object.keys(parsed.paths) : [];
			let endpointCount = 0;
			for (const path of paths) {
				endpointCount += Object.keys(parsed.paths[path]).filter((m) =>
					['get', 'post', 'put', 'delete', 'patch'].includes(m)
				).length;
			}
			return {
				endpoints: endpointCount,
				title: parsed.info?.title
			};
		} catch {
			// Try YAML-ish parsing for basic preview
			const pathMatches = spec.match(/^\s{2}\/[^\s:]+:/gm);
			return {
				endpoints: pathMatches?.length ?? 0
			};
		}
	}

	function updateOpenapiPreview(index: number) {
		const entry = openapiEntries[index];
		if (!entry) return;
		const preview = parseOpenapiPreview(entry.spec);
		openapiEntries[index].preview = preview;
		if (preview?.title && !entry.title) {
			openapiEntries[index].title = preview.title;
		}
	}

	function handleOpenapiFilesSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const files = input.files;
		if (!files || files.length === 0) return;

		// If the only entry is blank, remove it before appending
		const hasOnlyBlank =
			openapiEntries.length === 1 &&
			!openapiEntries[0].spec.trim() &&
			!openapiEntries[0].title.trim();

		const newEntries: OpenapiEntry[] = [];

		let filesRead = 0;
		const totalFiles = files.length;

		for (const file of Array.from(files)) {
			const reader = new FileReader();
			reader.onload = (e) => {
				const content = (e.target?.result as string) || '';
				const preview = parseOpenapiPreview(content);
				const title = preview?.title || file.name.replace(/\.[^.]+$/, '');
				newEntries.push({ spec: content, title, preview });
				filesRead++;

				if (filesRead === totalFiles) {
					if (hasOnlyBlank) {
						openapiEntries = newEntries;
					} else {
						openapiEntries = [...openapiEntries, ...newEntries];
					}
					openapiImportResults = null;
				}
			};
			reader.readAsText(file);
		}

		// Reset input so re-selecting the same files triggers onchange
		input.value = '';
	}

	async function submitAllOpenapi() {
		if (validOpenapiCount === 0) return;
		saving = true;
		error = '';
		success = '';
		openapiImportResults = null;

		const tags = openapiTags
			.split(',')
			.map((t) => t.trim())
			.filter(Boolean);

		const results: { title: string; success: boolean; error?: string }[] = [];

		for (const entry of openapiEntries) {
			if (!entry.spec.trim()) continue;

			const label = entry.title || 'Untitled Spec';
			try {
				await apiJson('/knowledge/documents/import-openapi', {
					method: 'POST',
					body: JSON.stringify({
						spec: entry.spec,
						title: entry.title || undefined,
						tags
					})
				});
				results.push({ title: label, success: true });
			} catch (e) {
				results.push({
					title: label,
					success: false,
					error: e instanceof Error ? e.message : 'Import failed'
				});
			}
		}

		openapiImportResults = results;

		const successCount = results.filter((r) => r.success).length;
		const errorCount = results.filter((r) => !r.success).length;

		if (errorCount === 0) {
			success = `${successCount} spec${successCount !== 1 ? 's' : ''} imported successfully.`;
			openapiEntries = [{ spec: '', title: '', preview: null }];
			openapiTags = '';
			onDocumentAdded?.();
		} else if (successCount === 0) {
			error = `All ${errorCount} spec${errorCount !== 1 ? 's' : ''} failed to import.`;
		} else {
			success = `${successCount} spec${successCount !== 1 ? 's' : ''} imported, ${errorCount} failed.`;
			onDocumentAdded?.();
		}

		saving = false;
	}
</script>

<div class="flex flex-col gap-4">
	<!-- Sub-tab bar -->
	<div class="flex gap-1 rounded-lg bg-surface-secondary p-1">
		{#each subTabs as tab}
			<button
				type="button"
				onclick={() => {
					activeSubTab = tab.id;
					error = '';
					success = '';
				}}
				class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors
					{activeSubTab === tab.id
					? 'bg-surface text-text-primary shadow-sm'
					: 'text-text-secondary hover:text-text-primary'}"
			>
				<tab.icon size={14} />
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- Feedback banners -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<AlertCircle size={16} />
			{error}
		</div>
	{/if}

	{#if success}
		<div
			class="flex items-center gap-2 rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success"
		>
			<CheckCircle2 size={16} />
			{success}
		</div>
	{/if}

	<!-- ================================================================= -->
	<!-- Text Input Tab                                                     -->
	<!-- ================================================================= -->
	{#if activeSubTab === 'text'}
		<form
			onsubmit={(e) => {
				e.preventDefault();
				submitText();
			}}
			class="flex flex-col gap-3"
		>
			<div class="grid grid-cols-2 gap-3">
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Title</span>
					<input
						type="text"
						bind:value={textForm.title}
						required
						placeholder="Document title"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Type</span>
					<select
						bind:value={textForm.type}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						{#each documentTypes as dt}
							<option value={dt.value}>{dt.label}</option>
						{/each}
					</select>
				</label>
			</div>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Content</span>
				<textarea
					bind:value={textForm.content}
					required
					rows={10}
					class="rounded-md border border-border bg-surface px-3 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-accent"
					placeholder="Paste or type document content..."
				></textarea>
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
				<input
					type="text"
					bind:value={textForm.tags}
					placeholder="e.g. runbook, onboarding, api-docs"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<div class="flex justify-end pt-1">
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
					Create Document
				</button>
			</div>
		</form>

	<!-- ================================================================= -->
	<!-- File Upload Tab                                                    -->
	<!-- ================================================================= -->
	{:else if activeSubTab === 'file'}
		<form
			onsubmit={(e) => {
				e.preventDefault();
				submitFiles();
			}}
			class="flex flex-col gap-3"
		>
			<!-- Drop zone -->
			<div
				role="button"
				tabindex="0"
				ondragover={(e) => {
					e.preventDefault();
					dragOver = true;
				}}
				ondragleave={() => (dragOver = false)}
				ondrop={handleFileDrop}
				onclick={() => document.getElementById('file-upload-input')?.click()}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						document.getElementById('file-upload-input')?.click();
					}
				}}
				class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 transition-colors
					{dragOver
					? 'border-accent bg-accent/5'
					: 'border-border hover:border-accent/50 hover:bg-surface-secondary/50'}"
			>
				{#if selectedFiles.length > 0}
					<!-- File list -->
					<div
						class="flex w-full flex-col gap-1"
						onclick={(e) => e.stopPropagation()}
						onkeydown={(e) => e.stopPropagation()}
						role="list"
					>
						{#each selectedFiles as file, index}
							<div class="flex items-center gap-2 rounded-md bg-surface px-3 py-1.5" role="listitem">
								<FileText size={16} class="shrink-0 text-accent" />
								<span class="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">
									{file.name}
								</span>
								<span class="shrink-0 text-xs text-text-secondary">
									{formatFileSize(file.size)}
								</span>
								<button
									type="button"
									onclick={() => removeFile(index)}
									class="shrink-0 rounded p-0.5 text-text-secondary hover:bg-danger/10 hover:text-danger"
									title="Remove file"
								>
									<X size={14} />
								</button>
							</div>
						{/each}
						<div class="flex items-center justify-between px-3 pt-1 text-xs text-text-secondary">
							<span>{selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected</span>
							<span>{formatFileSize(totalFileSize)} total</span>
						</div>
						<button
							type="button"
							onclick={() => clearFiles()}
							class="mt-1 self-center text-xs text-text-secondary hover:text-danger"
						>
							Clear all
						</button>
					</div>
				{:else}
					<Upload size={24} class="text-text-secondary" />
					<p class="text-sm text-text-secondary">
						Drop files here or <span class="text-accent">browse</span>
					</p>
					<p class="text-xs text-text-secondary">
						Supported: PDF, TXT, MD, HTML, JSON, YAML. Multiple files allowed.
					</p>
				{/if}
			</div>

			<input
				id="file-upload-input"
				type="file"
				multiple
				accept=".pdf,.txt,.md,.html,.json,.yaml,.yml,.csv,.xml"
				onchange={handleFileSelect}
				class="hidden"
			/>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
				<input
					type="text"
					bind:value={fileForm.tags}
					placeholder="e.g. runbook, onboarding"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<div class="flex justify-end pt-1">
				<button
					type="submit"
					disabled={saving || selectedFiles.length === 0}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Upload size={14} />
					{/if}
					Upload {selectedFiles.length || ''} File{selectedFiles.length !== 1 ? 's' : ''}
				</button>
			</div>

			<!-- Per-file upload results -->
			{#if uploadResults}
				<div class="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-secondary p-3">
					<span class="text-xs font-medium text-text-secondary">Upload Results</span>
					{#if uploadResults.documents && uploadResults.documents.length > 0}
						{#each uploadResults.documents as doc}
							<div class="flex items-center gap-2 text-sm">
								<CheckCircle2 size={14} class="shrink-0 text-success" />
								<span class="text-text-primary">{doc.filename}</span>
								<span class="text-xs text-text-secondary">({doc.status})</span>
							</div>
						{/each}
					{/if}
					{#if uploadResults.errors && uploadResults.errors.length > 0}
						{#each uploadResults.errors as err}
							<div class="flex items-center gap-2 text-sm">
								<AlertCircle size={14} class="shrink-0 text-danger" />
								<span class="text-text-primary">{err.filename}</span>
								<span class="text-xs text-danger">{err.error}</span>
							</div>
						{/each}
					{/if}
				</div>
			{/if}
		</form>

	<!-- ================================================================= -->
	<!-- URL Import Tab                                                     -->
	<!-- ================================================================= -->
	{:else if activeSubTab === 'url'}
		<form
			onsubmit={(e) => {
				e.preventDefault();
				submitUrl();
			}}
			class="flex flex-col gap-3"
		>
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">URL</span>
				<input
					type="url"
					bind:value={urlForm.url}
					required
					placeholder="https://example.com/docs/page"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Title (optional, auto-detected)</span
				>
				<input
					type="text"
					bind:value={urlForm.title}
					placeholder="Leave blank to auto-detect from page"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
				<input
					type="text"
					bind:value={urlForm.tags}
					placeholder="e.g. docs, external"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<div class="flex justify-end pt-1">
				<button
					type="submit"
					disabled={saving || !urlForm.url}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Globe size={14} />
					{/if}
					Import URL
				</button>
			</div>
		</form>

	<!-- ================================================================= -->
	<!-- OpenAPI Import Tab                                                 -->
	<!-- ================================================================= -->
	{:else if activeSubTab === 'openapi'}
		<form
			onsubmit={(e) => {
				e.preventDefault();
				submitAllOpenapi();
			}}
			class="flex flex-col gap-3"
		>
			<!-- Upload files button -->
			<div class="flex items-center gap-2">
				<label
					class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
				>
					<Upload size={14} />
					Upload files
					<input
						type="file"
						multiple
						accept=".json,.yaml,.yml"
						onchange={handleOpenapiFilesSelect}
						class="hidden"
					/>
				</label>
				<span class="text-xs text-text-secondary">.json / .yaml files</span>
			</div>

			<!-- Entry cards list -->
			<div class="flex flex-col gap-3">
				{#each openapiEntries as entry, index}
					<div class="relative flex flex-col gap-2 rounded-lg border border-border p-3">
						<!-- Entry header: number + title + remove -->
						<div class="flex items-center gap-2">
							<span class="text-xs font-medium text-text-secondary">
								Spec {index + 1}
							</span>
							<div class="flex-1">
								<input
									type="text"
									bind:value={entry.title}
									placeholder="Title (optional, auto-detected)"
									class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</div>
							{#if entry.preview}
								<span
									class="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent/5 px-2 py-0.5 text-xs text-accent"
								>
									<Code2 size={12} />
									{entry.preview.endpoints} endpoint{entry.preview.endpoints !== 1 ? 's' : ''}
								</span>
							{/if}
							{#if openapiEntries.length > 1}
								<button
									type="button"
									onclick={() => removeOpenapiEntry(index)}
									class="shrink-0 rounded p-1 text-text-secondary hover:bg-danger/10 hover:text-danger"
									title="Remove spec"
								>
									<X size={14} />
								</button>
							{/if}
						</div>

						<!-- Spec textarea -->
						<textarea
							bind:value={entry.spec}
							rows={8}
							oninput={() => updateOpenapiPreview(index)}
							class="rounded-md border border-border bg-surface px-3 py-1.5 font-mono text-xs text-text-primary outline-none focus:border-accent"
							placeholder={'{"openapi": "3.0.0", "info": {...}, "paths": {...}}'}
						></textarea>
					</div>
				{/each}
			</div>

			<!-- Add Spec button -->
			<button
				type="button"
				onclick={addOpenapiEntry}
				class="inline-flex items-center gap-1.5 self-start rounded-md border border-dashed border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-accent hover:text-accent"
			>
				<Plus size={14} />
				Add Spec
			</button>

			<!-- Shared tags -->
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Tags (comma-separated, applied to all)</span>
				<input
					type="text"
					bind:value={openapiTags}
					placeholder="e.g. api, openapi, rest"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<!-- Submit button -->
			<div class="flex justify-end pt-1">
				<button
					type="submit"
					disabled={saving || validOpenapiCount === 0}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Code2 size={14} />
					{/if}
					Import {validOpenapiCount} Spec{validOpenapiCount !== 1 ? 's' : ''}
				</button>
			</div>

			<!-- Per-spec import results -->
			{#if openapiImportResults}
				<div class="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-secondary p-3">
					<span class="text-xs font-medium text-text-secondary">Import Results</span>
					{#each openapiImportResults as result}
						<div class="flex items-center gap-2 text-sm">
							{#if result.success}
								<CheckCircle2 size={14} class="shrink-0 text-success" />
								<span class="text-text-primary">{result.title}</span>
							{:else}
								<AlertCircle size={14} class="shrink-0 text-danger" />
								<span class="text-text-primary">{result.title}</span>
								<span class="text-xs text-danger">{result.error}</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</form>

	<!-- ================================================================= -->
	<!-- GitHub Import Tab                                                  -->
	<!-- ================================================================= -->
	{:else if activeSubTab === 'github'}
		<KnowledgeGitHubImporter
			onsuccess={() => {
				success = 'Files imported successfully.';
				onDocumentAdded?.();
			}}
		/>
	{/if}
</div>
