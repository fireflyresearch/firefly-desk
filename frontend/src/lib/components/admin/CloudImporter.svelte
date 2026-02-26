<!--
  CloudImporter.svelte - 3-step wizard for importing documents from cloud sources.

  Step 1 (Connect): Select a configured document source.
  Step 2 (Browse): Navigate containers/drives and select files.
  Step 3 (Cart): Review selections, add tags, and import.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Cloud,
		HardDrive,
		Check,
		Loader2,
		FileText,
		AlertCircle,
		CheckCircle2,
		ShoppingCart,
		X,
		Trash2,
		Plus,
		ChevronRight,
		FolderOpen,
		Folder,
		ExternalLink,
		ArrowLeft
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		workspaces?: { id: string; name: string }[];
		onsuccess?: () => void;
	}

	let { workspaces = [], onsuccess }: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface DocumentSource {
		id: string;
		name: string;
		source_type: string;
		category: string;
		auth_method: string;
		is_active: boolean;
	}

	interface BrowseContainer {
		id: string;
		name: string;
		path: string;
	}

	interface BrowseItem {
		id: string;
		name: string;
		path: string;
		type: 'folder' | 'file';
		size: number | null;
		modified_at: string | null;
	}

	interface CartFile {
		id: string;
		name: string;
		path: string;
		size: number | null;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const WIZARD_STEPS: { id: 'connect' | 'browse' | 'cart'; label: string }[] = [
		{ id: 'connect', label: 'Connect' },
		{ id: 'browse', label: 'Browse' },
		{ id: 'cart', label: 'Cart' }
	];

	const IMPORTABLE_EXTENSIONS = new Set([
		'.pdf', '.txt', '.md', '.html', '.htm', '.json', '.yaml', '.yml',
		'.csv', '.xml', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
		'.rtf', '.rst', '.tex', '.log'
	]);

	// -----------------------------------------------------------------------
	// State -- step tracking
	// -----------------------------------------------------------------------

	let step = $state<'connect' | 'browse' | 'cart'>('connect');

	// -----------------------------------------------------------------------
	// State -- source selection
	// -----------------------------------------------------------------------

	let sources = $state<DocumentSource[]>([]);
	let selectedSourceId = $state('');
	let loadingSources = $state(true);
	let error = $state('');

	// -----------------------------------------------------------------------
	// State -- browse
	// -----------------------------------------------------------------------

	let containers = $state<BrowseContainer[]>([]);
	let selectedContainer = $state<BrowseContainer | null>(null);
	let browseItems = $state<BrowseItem[]>([]);
	let breadcrumb = $state<{ id: string; name: string }[]>([]);
	let loadingContainers = $state(false);
	let loadingItems = $state(false);
	let selectedFiles = $state<Set<string>>(new Set());

	// -----------------------------------------------------------------------
	// State -- cart
	// -----------------------------------------------------------------------

	let cart = $state<CartFile[]>([]);
	let importTags = $state('');
	let selectedWorkspaceIds = $state<string[]>([]);
	let importing = $state(false);
	let importResult = $state<{ status: string; message?: string } | null>(null);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let selectedSource = $derived(sources.find((s) => s.id === selectedSourceId));

	let blobSources = $derived(sources.filter((s) => s.category === 'blob_storage' && s.is_active));
	let driveSources = $derived(sources.filter((s) => s.category === 'drive' && s.is_active));

	let totalCartFiles = $derived(cart.length);

	let filteredBrowseItems = $derived.by(() => {
		return browseItems.filter((item) => {
			if (item.type === 'folder') return true;
			const ext = getExtension(item.name);
			return IMPORTABLE_EXTENSIONS.has(ext);
		});
	});

	let selectedFileCount = $derived(selectedFiles.size);

	// -----------------------------------------------------------------------
	// Source loading
	// -----------------------------------------------------------------------

	async function loadSources() {
		loadingSources = true;
		error = '';
		try {
			const all = await apiJson<DocumentSource[]>('/admin/document-sources');
			sources = all.filter((s) => s.is_active);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load document sources';
		} finally {
			loadingSources = false;
		}
	}

	// Initial load
	$effect(() => {
		loadSources();
	});

	// -----------------------------------------------------------------------
	// Connect
	// -----------------------------------------------------------------------

	async function connectSource() {
		if (!selectedSourceId) return;
		loadingContainers = true;
		error = '';
		try {
			const result = await apiJson<{ containers: BrowseContainer[] }>(
				`/import/${encodeURIComponent(selectedSourceId)}/browse`
			);
			containers = result.containers ?? [];
			step = 'browse';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to connect to source';
		} finally {
			loadingContainers = false;
		}
	}

	// -----------------------------------------------------------------------
	// Browse -- navigate
	// -----------------------------------------------------------------------

	async function selectContainer(container: BrowseContainer) {
		selectedContainer = container;
		breadcrumb = [{ id: container.id, name: container.name }];
		selectedFiles = new Set();
		await loadBrowseItems(container.id);
	}

	async function loadBrowseItems(rootId: string) {
		loadingItems = true;
		error = '';
		try {
			const result = await apiJson<{ items: BrowseItem[] }>(
				`/import/${encodeURIComponent(selectedSourceId)}/browse/${encodeURIComponent(rootId)}`
			);
			browseItems = result.items ?? [];
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load items';
		} finally {
			loadingItems = false;
		}
	}

	async function navigateFolder(folder: BrowseItem) {
		breadcrumb = [...breadcrumb, { id: folder.id, name: folder.name }];
		selectedFiles = new Set();
		await loadBrowseItems(folder.id);
	}

	async function navigateBreadcrumb(index: number) {
		breadcrumb = breadcrumb.slice(0, index + 1);
		const target = breadcrumb[breadcrumb.length - 1];
		selectedFiles = new Set();
		await loadBrowseItems(target.id);
	}

	// -----------------------------------------------------------------------
	// Browse -- file selection
	// -----------------------------------------------------------------------

	function toggleFile(item: BrowseItem) {
		const next = new Set(selectedFiles);
		if (next.has(item.id)) {
			next.delete(item.id);
		} else {
			next.add(item.id);
		}
		selectedFiles = next;
	}

	function selectAllVisible() {
		const fileItems = filteredBrowseItems.filter((i) => i.type === 'file');
		selectedFiles = new Set(fileItems.map((i) => i.id));
	}

	function deselectAll() {
		selectedFiles = new Set();
	}

	function addSelectedToCart() {
		const fileItems = filteredBrowseItems.filter(
			(i) => i.type === 'file' && selectedFiles.has(i.id)
		);
		// Avoid duplicates in cart
		const existingIds = new Set(cart.map((c) => c.id));
		const newItems: CartFile[] = fileItems
			.filter((i) => !existingIds.has(i.id))
			.map((i) => ({
				id: i.id,
				name: i.name,
				path: i.path,
				size: i.size
			}));
		cart = [...cart, ...newItems];
		selectedFiles = new Set();
	}

	// -----------------------------------------------------------------------
	// Cart operations
	// -----------------------------------------------------------------------

	function removeCartItem(index: number) {
		cart = cart.filter((_, i) => i !== index);
	}

	function clearCart() {
		cart = [];
	}

	// -----------------------------------------------------------------------
	// Import
	// -----------------------------------------------------------------------

	async function importFiles() {
		if (cart.length === 0 || !selectedSourceId) return;
		importing = true;
		error = '';
		importResult = null;

		const tags = importTags
			.split(',')
			.map((t) => t.trim())
			.filter(Boolean);

		const payload = {
			file_ids: cart.map((f) => f.id),
			paths: cart.map((f) => f.path),
			tags,
			workspace_ids: selectedWorkspaceIds.length > 0 ? selectedWorkspaceIds : undefined
		};

		try {
			const result = await apiJson<{ status: string; message?: string }>(
				`/import/${encodeURIComponent(selectedSourceId)}/import`,
				{
					method: 'POST',
					body: JSON.stringify(payload)
				}
			);
			importResult = result;
			cart = [];
			onsuccess?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Import failed';
		} finally {
			importing = false;
		}
	}

	// -----------------------------------------------------------------------
	// Reset
	// -----------------------------------------------------------------------

	function disconnect() {
		step = 'connect';
		containers = [];
		selectedContainer = null;
		browseItems = [];
		breadcrumb = [];
		selectedFiles = new Set();
		cart = [];
		importTags = '';
		importResult = null;
		error = '';
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function getExtension(name: string): string {
		const dot = name.lastIndexOf('.');
		return dot >= 0 ? name.slice(dot).toLowerCase() : '';
	}

	function formatBytes(bytes: number | null): string {
		if (bytes === null || bytes === undefined) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function sourceTypeLabel(type: string): string {
		const labels: Record<string, string> = {
			s3: 'S3',
			azure_blob: 'Azure Blob',
			gcs: 'GCS',
			onedrive: 'OneDrive',
			sharepoint: 'SharePoint',
			google_drive: 'Google Drive'
		};
		return labels[type] ?? type;
	}
</script>

<div class="flex flex-col gap-4">
	<!-- Step indicator -->
	<div class="flex items-center gap-2 text-xs">
		{#each WIZARD_STEPS as s, i}
			{#if i > 0}
				<div
					class="h-px w-6 {step === s.id || (s.id === 'browse' && step === 'cart') || (s.id === 'connect' && step !== 'connect') ? 'bg-accent' : 'bg-border'}"
				></div>
			{/if}
			<button
				type="button"
				disabled={s.id === 'connect' ? false : s.id === 'browse' ? step === 'connect' : step === 'connect'}
				onclick={() => {
					if (s.id === 'connect' || step !== 'connect') {
						step = s.id;
						error = '';
					}
				}}
				class="flex items-center gap-1.5"
			>
				<div
					class="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-medium transition-colors
						{step === s.id
						? 'bg-accent text-white'
						: (s.id === 'connect' && step !== 'connect') || (s.id === 'browse' && step === 'cart')
							? 'bg-accent/20 text-accent'
							: 'bg-surface-secondary text-text-tertiary'}"
				>
					{#if (s.id === 'connect' && step !== 'connect') || (s.id === 'browse' && step === 'cart')}
						<Check size={10} />
					{:else}
						{i + 1}
					{/if}
				</div>
				<span
					class="{step === s.id ? 'font-medium text-text-primary' : 'text-text-tertiary'}"
				>
					{s.label}
				</span>
				{#if s.id === 'cart' && totalCartFiles > 0}
					<span
						class="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-bold text-white"
					>
						{totalCartFiles}
					</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Error banner -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<AlertCircle size={16} />
			{error}
		</div>
	{/if}

	<!-- ================================================================= -->
	<!-- Step 1: Connect                                                    -->
	<!-- ================================================================= -->
	{#if step === 'connect'}
		<div class="flex flex-col gap-4">
			<div class="flex items-center gap-2">
				<Cloud size={20} class="text-text-primary" />
				<h3 class="text-sm font-semibold text-text-primary">Select Cloud Source</h3>
			</div>

			{#if loadingSources}
				<div class="flex items-center justify-center py-8">
					<Loader2 size={20} class="animate-spin text-accent" />
				</div>
			{:else if sources.length === 0}
				<div class="rounded-xl border border-border bg-surface-secondary p-5 text-center">
					<Cloud size={24} class="mx-auto mb-2 text-text-tertiary" />
					<p class="text-sm text-text-secondary">No document sources configured.</p>
					<a
						href="/admin/document-sources"
						class="mt-2 inline-flex items-center gap-1 text-sm text-accent hover:underline"
					>
						Configure sources
						<ExternalLink size={12} />
					</a>
				</div>
			{:else}
				<p class="text-xs text-text-secondary">
					Select a configured cloud source to browse and import documents.
				</p>

				<!-- Source selector grouped by category -->
				{#if blobSources.length > 0}
					<div class="flex flex-col gap-1.5">
						<span class="text-xs font-medium text-text-secondary">
							<HardDrive size={12} class="mb-0.5 mr-1 inline-block" />
							Blob Storage
						</span>
						<div class="flex flex-wrap gap-2">
							{#each blobSources as source}
								<button
									type="button"
									onclick={() => (selectedSourceId = source.id)}
									class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors
										{selectedSourceId === source.id
										? 'border-accent bg-accent/10 text-accent'
										: 'border-border text-text-primary hover:bg-surface-secondary'}"
								>
									<HardDrive size={14} />
									<div class="text-left">
										<div class="font-medium">{source.name}</div>
										<div class="text-[10px] text-text-secondary">{sourceTypeLabel(source.source_type)}</div>
									</div>
								</button>
							{/each}
						</div>
					</div>
				{/if}

				{#if driveSources.length > 0}
					<div class="flex flex-col gap-1.5">
						<span class="text-xs font-medium text-text-secondary">
							<Cloud size={12} class="mb-0.5 mr-1 inline-block" />
							Drive
						</span>
						<div class="flex flex-wrap gap-2">
							{#each driveSources as source}
								<button
									type="button"
									onclick={() => (selectedSourceId = source.id)}
									class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors
										{selectedSourceId === source.id
										? 'border-accent bg-accent/10 text-accent'
										: 'border-border text-text-primary hover:bg-surface-secondary'}"
								>
									<Cloud size={14} />
									<div class="text-left">
										<div class="font-medium">{source.name}</div>
										<div class="text-[10px] text-text-secondary">{sourceTypeLabel(source.source_type)}</div>
									</div>
								</button>
							{/each}
						</div>
					</div>
				{/if}

				<div class="flex justify-end pt-1">
					<button
						type="button"
						disabled={!selectedSourceId || loadingContainers}
						onclick={connectSource}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if loadingContainers}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Cloud size={14} />
						{/if}
						Connect
					</button>
				</div>
			{/if}
		</div>

	<!-- ================================================================= -->
	<!-- Step 2: Browse                                                     -->
	<!-- ================================================================= -->
	{:else if step === 'browse'}
		<div class="flex flex-col gap-3">
			<!-- Connected source info + disconnect -->
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<Cloud size={14} class="text-accent" />
					<span class="text-xs font-medium text-text-primary">
						{selectedSource?.name ?? 'Connected'}
					</span>
					<span class="rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
						{selectedSource ? sourceTypeLabel(selectedSource.source_type) : ''}
					</span>
				</div>
				<button
					type="button"
					onclick={disconnect}
					class="text-xs text-text-secondary hover:text-danger"
				>
					Disconnect
				</button>
			</div>

			<!-- Container / Drive selector -->
			{#if !selectedContainer}
				<div class="flex flex-col gap-2">
					<span class="text-xs font-medium text-text-secondary">
						{selectedSource?.category === 'blob_storage' ? 'Select Container' : 'Select Drive'}
					</span>
					{#if containers.length > 0}
						<div class="flex max-h-48 flex-col gap-0.5 overflow-y-auto rounded-md border border-border p-1">
							{#each containers as container}
								<button
									type="button"
									onclick={() => selectContainer(container)}
									class="flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-text-primary transition-colors hover:bg-surface-secondary"
								>
									<FolderOpen size={14} class="shrink-0 text-accent" />
									<div class="min-w-0 flex-1">
										<div class="truncate font-medium">{container.name}</div>
										{#if container.path}
											<div class="truncate text-[10px] text-text-secondary">{container.path}</div>
										{/if}
									</div>
									<ChevronRight size={12} class="shrink-0 text-text-tertiary" />
								</button>
							{/each}
						</div>
					{:else}
						<p class="py-6 text-center text-xs text-text-secondary">
							No containers or drives found.
						</p>
					{/if}
				</div>
			{:else}
				<!-- Breadcrumb navigation -->
				<div class="flex items-center gap-1 text-xs">
					<button
						type="button"
						onclick={() => {
							selectedContainer = null;
							browseItems = [];
							breadcrumb = [];
							selectedFiles = new Set();
						}}
						class="text-accent hover:underline"
					>
						{selectedSource?.category === 'blob_storage' ? 'Containers' : 'Drives'}
					</button>
					{#each breadcrumb as crumb, i}
						<ChevronRight size={10} class="text-text-tertiary" />
						{#if i < breadcrumb.length - 1}
							<button
								type="button"
								onclick={() => navigateBreadcrumb(i)}
								class="text-accent hover:underline"
							>
								{crumb.name}
							</button>
						{:else}
							<span class="font-medium text-text-primary">{crumb.name}</span>
						{/if}
					{/each}
				</div>

				<!-- File list -->
				{#if loadingItems}
					<div class="flex items-center justify-center py-6">
						<Loader2 size={16} class="animate-spin text-accent" />
					</div>
				{:else if filteredBrowseItems.length > 0}
					<!-- Bulk actions -->
					<div class="flex items-center justify-between">
						<span class="text-[11px] text-text-secondary">
							{selectedFileCount} selected
						</span>
						<div class="flex gap-1.5">
							<button
								type="button"
								onclick={selectAllVisible}
								class="text-[11px] text-accent hover:underline"
							>
								Select all files
							</button>
							{#if selectedFileCount > 0}
								<button
									type="button"
									onclick={deselectAll}
									class="text-[11px] text-text-secondary hover:text-danger"
								>
									Clear
								</button>
							{/if}
						</div>
					</div>

					<div
						class="flex max-h-64 flex-col gap-0.5 overflow-y-auto rounded-md border border-border p-1"
					>
						{#each filteredBrowseItems as item}
							{#if item.type === 'folder'}
								<button
									type="button"
									onclick={() => navigateFolder(item)}
									class="flex items-center gap-1.5 rounded px-2 py-1.5 text-left transition-colors hover:bg-surface-secondary"
								>
									<Folder size={12} class="shrink-0 text-accent" />
									<span class="min-w-0 flex-1 truncate text-xs font-medium text-text-primary">
										{item.name}
									</span>
									<ChevronRight size={12} class="shrink-0 text-text-tertiary" />
								</button>
							{:else}
								<label
									class="flex cursor-pointer items-center gap-1.5 rounded px-2 py-1 transition-colors hover:bg-surface-secondary"
								>
									<input
										type="checkbox"
										checked={selectedFiles.has(item.id)}
										onchange={() => toggleFile(item)}
										class="h-3 w-3 rounded border-border accent-accent"
									/>
									<FileText size={11} class="shrink-0 text-text-tertiary" />
									<span class="min-w-0 flex-1 truncate text-[11px] text-text-primary">
										{item.name}
									</span>
									{#if item.size !== null}
										<span class="shrink-0 text-[9px] text-text-tertiary">
											{formatBytes(item.size)}
										</span>
									{/if}
								</label>
							{/if}
						{/each}
					</div>

					<!-- Add to Cart button -->
					{#if selectedFileCount > 0}
						<button
							type="button"
							onclick={addSelectedToCart}
							class="inline-flex items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
						>
							<Plus size={12} />
							Add {selectedFileCount} file{selectedFileCount !== 1 ? 's' : ''} to Cart
						</button>
					{/if}
				{:else}
					<p class="py-6 text-center text-xs text-text-secondary">
						No importable files found in this location.
					</p>
				{/if}
			{/if}

			<!-- Bottom bar: cart badge + go to cart -->
			{#if totalCartFiles > 0}
				<div class="flex items-center justify-between rounded-lg border border-accent/30 bg-accent/5 px-4 py-2">
					<div class="flex items-center gap-2">
						<ShoppingCart size={14} class="text-accent" />
						<span class="text-xs font-medium text-text-primary">
							{totalCartFiles} file{totalCartFiles !== 1 ? 's' : ''} in cart
						</span>
					</div>
					<button
						type="button"
						onclick={() => (step = 'cart')}
						class="inline-flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
					>
						<ShoppingCart size={12} />
						Review Cart
					</button>
				</div>
			{/if}
		</div>

	<!-- ================================================================= -->
	<!-- Step 3: Cart & Import                                              -->
	<!-- ================================================================= -->
	{:else if step === 'cart'}
		<div class="flex flex-col gap-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<ShoppingCart size={16} class="text-text-primary" />
					<h3 class="text-sm font-semibold text-text-primary">Import Cart</h3>
					<span class="text-xs text-text-secondary">
						{totalCartFiles} file{totalCartFiles !== 1 ? 's' : ''}
					</span>
				</div>
				<button
					type="button"
					onclick={() => (step = 'browse')}
					class="inline-flex items-center gap-1 text-xs text-accent hover:underline"
				>
					<Plus size={12} />
					Browse More
				</button>
			</div>

			{#if cart.length === 0 && !importResult}
				<div class="rounded-xl border border-border bg-surface-secondary p-6 text-center">
					<ShoppingCart size={24} class="mx-auto mb-2 text-text-tertiary" />
					<p class="text-sm text-text-secondary">Your cart is empty.</p>
					<button
						type="button"
						onclick={() => (step = 'browse')}
						class="mt-2 text-sm text-accent hover:underline"
					>
						Browse files to add
					</button>
				</div>
			{:else}
				<!-- Cart items list -->
				<div class="rounded-lg border border-border bg-surface p-3">
					<div class="mb-2 flex items-center justify-between">
						<div class="flex items-center gap-2">
							<Cloud size={12} class="text-accent" />
							<span class="text-xs font-medium text-text-primary">
								{selectedSource?.name ?? 'Source'}
							</span>
							<span class="rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
								{selectedSource ? sourceTypeLabel(selectedSource.source_type) : ''}
							</span>
						</div>
						<button
							type="button"
							onclick={clearCart}
							class="inline-flex items-center gap-1 text-[11px] text-text-secondary hover:text-danger"
						>
							<Trash2 size={10} />
							Clear all
						</button>
					</div>
					<div class="flex flex-col gap-0.5">
						{#each cart as file, index}
							<div class="flex items-center gap-1.5 rounded px-2 py-0.5">
								<FileText size={10} class="shrink-0 text-text-tertiary" />
								<span class="min-w-0 flex-1 truncate text-[11px] text-text-primary">
									{file.path || file.name}
								</span>
								{#if file.size !== null}
									<span class="shrink-0 text-[9px] text-text-tertiary">
										{formatBytes(file.size)}
									</span>
								{/if}
								<button
									type="button"
									onclick={() => removeCartItem(index)}
									class="shrink-0 rounded p-0.5 text-text-tertiary hover:text-danger"
									title="Remove file"
								>
									<X size={10} />
								</button>
							</div>
						{/each}
					</div>
				</div>

				<!-- Tags input -->
				{#if cart.length > 0}
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
						<input
							type="text"
							bind:value={importTags}
							placeholder="e.g. cloud-import, docs"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<!-- Workspace selector -->
					{#if workspaces.length > 0}
						<div class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Workspaces</span>
							<div class="flex flex-wrap gap-1.5">
								{#each workspaces as ws}
									<button
										type="button"
										onclick={() => {
											if (selectedWorkspaceIds.includes(ws.id)) {
												selectedWorkspaceIds = selectedWorkspaceIds.filter((id) => id !== ws.id);
											} else {
												selectedWorkspaceIds = [...selectedWorkspaceIds, ws.id];
											}
										}}
										class="rounded-full px-3 py-1 text-xs font-medium transition-colors
											{selectedWorkspaceIds.includes(ws.id)
											? 'bg-accent text-white'
											: 'bg-surface-secondary text-text-secondary hover:bg-surface-hover'}"
									>
										{ws.name}
									</button>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Import button -->
					<div class="flex justify-end">
						<button
							type="button"
							disabled={importing || cart.length === 0}
							onclick={importFiles}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if importing}
								<Loader2 size={14} class="animate-spin" />
								Importing...
							{:else}
								<Cloud size={14} />
								Import {totalCartFiles} File{totalCartFiles !== 1 ? 's' : ''}
							{/if}
						</button>
					</div>
				{/if}

				<!-- Import result -->
				{#if importResult}
					<div class="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-secondary p-3">
						<div class="mb-1 flex items-center gap-2">
							<CheckCircle2 size={14} class="text-success" />
							<span class="text-xs font-medium text-text-primary">Import Submitted</span>
						</div>
						<p class="text-xs text-text-secondary">
							{importResult.message || 'Your files have been queued for import. They will appear in the knowledge base shortly.'}
						</p>
						<button
							type="button"
							onclick={() => {
								importResult = null;
								step = 'browse';
							}}
							class="mt-2 self-start text-xs text-accent hover:underline"
						>
							Import more files
						</button>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>
