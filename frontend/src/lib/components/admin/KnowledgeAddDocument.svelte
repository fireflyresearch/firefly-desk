<!--
  KnowledgeAddDocument.svelte - Multi-method document ingestion form.

  Provides four sub-tabs for adding documents to the knowledge base:
  Text input, File upload, URL import, and OpenAPI import.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		FileText,
		Upload,
		Globe,
		Code2,
		Loader2,
		Save,
		X,
		CheckCircle2,
		AlertCircle
	} from 'lucide-svelte';
	import { apiJson, apiFetch, getToken } from '$lib/services/api.js';

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

	type SubTab = 'text' | 'file' | 'url' | 'openapi';

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
		title: '',
		tags: ''
	});
	let selectedFile = $state<File | null>(null);
	let dragOver = $state(false);

	// URL import
	let urlForm = $state({
		url: '',
		title: '',
		tags: ''
	});
	let urlPreview = $state<{ title?: string; description?: string } | null>(null);
	let fetchingPreview = $state(false);

	// OpenAPI import
	let openapiForm = $state({
		spec: '',
		title: '',
		tags: ''
	});
	let openapiFile = $state<File | null>(null);
	let openapiPreview = $state<{ endpoints: number; title?: string } | null>(null);

	// -----------------------------------------------------------------------
	// Sub-tab definitions
	// -----------------------------------------------------------------------

	const subTabs: { id: SubTab; label: string; icon: typeof FileText }[] = [
		{ id: 'text', label: 'Text', icon: FileText },
		{ id: 'file', label: 'File Upload', icon: Upload },
		{ id: 'url', label: 'URL Import', icon: Globe },
		{ id: 'openapi', label: 'OpenAPI Import', icon: Code2 }
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
		const file = event.dataTransfer?.files[0];
		if (file) {
			selectedFile = file;
			if (!fileForm.title) {
				fileForm.title = file.name.replace(/\.[^.]+$/, '');
			}
		}
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (file) {
			selectedFile = file;
			if (!fileForm.title) {
				fileForm.title = file.name.replace(/\.[^.]+$/, '');
			}
		}
	}

	function clearFile() {
		selectedFile = null;
		fileForm.title = '';
	}

	async function submitFile() {
		if (!selectedFile) return;
		saving = true;
		error = '';
		success = '';

		const formData = new FormData();
		formData.append('file', selectedFile);
		formData.append('title', fileForm.title);
		if (fileForm.tags) {
			formData.append('tags', fileForm.tags);
		}

		try {
			const headers: Record<string, string> = {};
			const token = getToken();
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}

			const response = await fetch('/api/knowledge/documents/import-file', {
				method: 'POST',
				headers,
				body: formData
			});

			if (!response.ok) {
				const body = await response.text().catch(() => '');
				throw new Error(`API ${response.status}: ${body}`);
			}

			success = 'File imported successfully.';
			selectedFile = null;
			fileForm = { title: '', tags: '' };
			onDocumentAdded?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to upload file';
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

	function handleOpenapiFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (file) {
			openapiFile = file;
			if (!openapiForm.title) {
				openapiForm.title = file.name.replace(/\.[^.]+$/, '');
			}
			const reader = new FileReader();
			reader.onload = (e) => {
				openapiForm.spec = (e.target?.result as string) || '';
				parseOpenapiPreview(openapiForm.spec);
			};
			reader.readAsText(file);
		}
	}

	function parseOpenapiPreview(spec: string) {
		try {
			const parsed = JSON.parse(spec);
			const paths = parsed.paths ? Object.keys(parsed.paths) : [];
			let endpointCount = 0;
			for (const path of paths) {
				endpointCount += Object.keys(parsed.paths[path]).filter((m) =>
					['get', 'post', 'put', 'delete', 'patch'].includes(m)
				).length;
			}
			openapiPreview = {
				endpoints: endpointCount,
				title: parsed.info?.title
			};
			if (!openapiForm.title && parsed.info?.title) {
				openapiForm.title = parsed.info.title;
			}
		} catch {
			// Try YAML-ish parsing for basic preview
			const pathMatches = spec.match(/^\s{2}\/[^\s:]+:/gm);
			openapiPreview = {
				endpoints: pathMatches?.length ?? 0
			};
		}
	}

	async function submitOpenapi() {
		saving = true;
		error = '';
		success = '';

		const payload = {
			spec: openapiForm.spec,
			title: openapiForm.title || undefined,
			tags: openapiForm.tags
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean)
		};

		try {
			await apiJson('/knowledge/documents/import-openapi', {
				method: 'POST',
				body: JSON.stringify(payload)
			});
			success = 'OpenAPI spec imported successfully.';
			openapiForm = { spec: '', title: '', tags: '' };
			openapiFile = null;
			openapiPreview = null;
			onDocumentAdded?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to import OpenAPI spec';
		} finally {
			saving = false;
		}
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
			class="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<AlertCircle size={16} />
			{error}
		</div>
	{/if}

	{#if success}
		<div
			class="flex items-center gap-2 rounded-md border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success"
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
				submitFile();
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
				{#if selectedFile}
					<div class="flex items-center gap-2">
						<FileText size={20} class="text-accent" />
						<span class="text-sm font-medium text-text-primary">{selectedFile.name}</span>
						<span class="text-xs text-text-secondary">
							({(selectedFile.size / 1024).toFixed(1)} KB)
						</span>
						<button
							type="button"
							onclick={(e) => {
								e.stopPropagation();
								clearFile();
							}}
							class="ml-2 rounded p-0.5 text-text-secondary hover:bg-danger/10 hover:text-danger"
						>
							<X size={14} />
						</button>
					</div>
				{:else}
					<Upload size={24} class="text-text-secondary" />
					<p class="text-sm text-text-secondary">
						Drop a file here or <span class="text-accent">browse</span>
					</p>
					<p class="text-xs text-text-secondary">
						Supported: PDF, TXT, MD, HTML, JSON, YAML
					</p>
				{/if}
			</div>

			<input
				id="file-upload-input"
				type="file"
				accept=".pdf,.txt,.md,.html,.json,.yaml,.yml,.csv,.xml"
				onchange={handleFileSelect}
				class="hidden"
			/>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Title</span>
				<input
					type="text"
					bind:value={fileForm.title}
					required
					placeholder="Auto-populated from filename"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

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
					disabled={saving || !selectedFile}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Upload size={14} />
					{/if}
					Upload File
				</button>
			</div>
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
				submitOpenapi();
			}}
			class="flex flex-col gap-3"
		>
			<div class="flex items-center gap-3">
				<label class="flex flex-1 flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary"
						>Title (optional, auto-detected)</span
					>
					<input
						type="text"
						bind:value={openapiForm.title}
						placeholder="API spec title"
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
				</label>

				<div class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Or upload file</span>
					<label
						class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						<Upload size={14} />
						{openapiFile ? openapiFile.name : 'Choose file'}
						<input
							type="file"
							accept=".json,.yaml,.yml"
							onchange={handleOpenapiFileSelect}
							class="hidden"
						/>
					</label>
				</div>
			</div>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">OpenAPI Spec (JSON or YAML)</span>
				<textarea
					bind:value={openapiForm.spec}
					required
					rows={12}
					oninput={() => {
						if (openapiForm.spec.length > 10) {
							parseOpenapiPreview(openapiForm.spec);
						}
					}}
					class="rounded-md border border-border bg-surface px-3 py-1.5 font-mono text-xs text-text-primary outline-none focus:border-accent"
					placeholder={'{"openapi": "3.0.0", "info": {...}, "paths": {...}}'}
				></textarea>
			</label>

			{#if openapiPreview}
				<div
					class="flex items-center gap-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-sm"
				>
					<Code2 size={14} class="text-accent" />
					<span class="text-text-primary">
						{#if openapiPreview.title}
							<strong>{openapiPreview.title}</strong> &mdash;
						{/if}
						{openapiPreview.endpoints} endpoint{openapiPreview.endpoints !== 1 ? 's' : ''} detected
					</span>
				</div>
			{/if}

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
				<input
					type="text"
					bind:value={openapiForm.tags}
					placeholder="e.g. api, openapi, rest"
					class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
				/>
			</label>

			<div class="flex justify-end pt-1">
				<button
					type="submit"
					disabled={saving || !openapiForm.spec}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
					{:else}
						<Code2 size={14} />
					{/if}
					Import OpenAPI Spec
				</button>
			</div>
		</form>
	{/if}
</div>
