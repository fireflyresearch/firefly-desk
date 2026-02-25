<!--
  FileViewerModal.svelte - Full-screen modal overlay for previewing uploaded files.

  Supports PDF (iframe), images (img), DOCX (rendered HTML), XLSX (interactive
  table with sheet tabs), PPTX (slide carousel with prev/next), and plain text (pre).
  Fetches rendered content from GET /api/files/{fileId}/render.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { fade, fly } from 'svelte/transition';
	import { X, Download, ChevronLeft, ChevronRight } from 'lucide-svelte';

	interface FileViewerModalProps {
		fileId: string;
		fileName: string;
		contentType: string;
		onClose: () => void;
	}

	let { fileId, fileName, contentType, onClose }: FileViewerModalProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let renderData: any = $state(null);
	let loading = $state(true);
	let error = $state('');
	let activeSheet = $state(0);
	let activeSlide = $state(0);

	// -----------------------------------------------------------------------
	// Derived helpers
	// -----------------------------------------------------------------------

	let isImage = $derived(contentType.startsWith('image/'));
	let isPdf = $derived(contentType === 'application/pdf');
	let isDocx = $derived(
		contentType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
	);
	let isXlsx = $derived(
		contentType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
	);
	let isPptx = $derived(
		contentType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
	);
	let isText = $derived(
		contentType.startsWith('text/') || contentType === 'application/json'
	);

	let needsRender = $derived(isDocx || isXlsx || isPptx || isText);

	let sheetNames: string[] = $derived(
		renderData?.sheets ? renderData.sheets.map((s: any) => s.name) : []
	);

	let currentSheetRows: any[][] = $derived(
		renderData?.sheets?.[activeSheet]?.rows ?? []
	);

	let slides: any[] = $derived(renderData?.slides ?? []);

	let totalSlides = $derived(slides.length);

	// -----------------------------------------------------------------------
	// Fetch rendered content
	// -----------------------------------------------------------------------

	$effect(() => {
		if (!needsRender) {
			loading = false;
			return;
		}

		loading = true;
		error = '';
		renderData = null;

		fetch(`/api/files/${fileId}/render`)
			.then((res) => {
				if (!res.ok) throw new Error(`Failed to load file preview (${res.status})`);
				return res.json();
			})
			.then((data) => {
				renderData = data;
				loading = false;
			})
			.catch((err) => {
				error = err.message ?? 'Failed to load file preview';
				loading = false;
			});
	});

	// -----------------------------------------------------------------------
	// Keyboard navigation
	// -----------------------------------------------------------------------

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		} else if (isPptx && e.key === 'ArrowLeft') {
			prevSlide();
		} else if (isPptx && e.key === 'ArrowRight') {
			nextSlide();
		}
	}

	function prevSlide() {
		if (activeSlide > 0) activeSlide--;
	}

	function nextSlide() {
		if (activeSlide < totalSlides - 1) activeSlide++;
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
	transition:fade={{ duration: 150 }}
	onclick={onClose}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClose(); }}
	role="dialog"
	aria-modal="true"
	aria-label="File preview: {fileName}"
	tabindex="-1"
>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="relative flex h-[90vh] w-[90vw] max-w-6xl flex-col overflow-hidden rounded-2xl bg-surface shadow-2xl"
		transition:fly={{ y: 20, duration: 200 }}
		onclick={(e) => { e.stopPropagation(); }}
		onkeydown={(e) => { e.stopPropagation(); }}
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-border px-5 py-3">
			<h2 class="truncate text-sm font-semibold text-text-primary">{fileName}</h2>
			<div class="flex items-center gap-1.5">
				<a
					href="/api/files/{fileId}/download"
					download
					class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary"
					title="Download file"
				>
					<Download size={16} />
				</a>
				<button
					type="button"
					class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary"
					onclick={onClose}
					title="Close"
				>
					<X size={16} />
				</button>
			</div>
		</div>

		<!-- Content area -->
		<div class="flex-1 overflow-auto">
			{#if loading}
				<!-- Loading spinner -->
				<div class="flex h-full items-center justify-center">
					<div class="flex flex-col items-center gap-3">
						<div class="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
						<p class="text-sm text-text-secondary">Loading preview...</p>
					</div>
				</div>
			{:else if error}
				<!-- Error state -->
				<div class="flex h-full items-center justify-center">
					<div class="flex flex-col items-center gap-3 px-6 text-center">
						<div class="flex h-12 w-12 items-center justify-center rounded-full bg-danger/10">
							<X size={24} class="text-danger" />
						</div>
						<p class="text-sm font-medium text-text-primary">Preview unavailable</p>
						<p class="max-w-md text-xs text-text-secondary">{error}</p>
						<a
							href="/api/files/{fileId}/download"
							download
							class="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90"
						>
							<Download size={14} />
							Download instead
						</a>
					</div>
				</div>
			{:else if isPdf}
				<!-- PDF via iframe -->
				<iframe
					src="/api/files/{fileId}/download"
					title="PDF preview: {fileName}"
					class="h-full w-full border-0"
				></iframe>
			{:else if isImage}
				<!-- Image -->
				<div class="flex h-full items-center justify-center bg-surface-secondary p-4">
					<img
						src="/api/files/{fileId}/download"
						alt={fileName}
						class="max-h-full max-w-full object-contain"
					/>
				</div>
			{:else if isDocx}
				<!-- DOCX rendered HTML -->
				<div class="prose prose-sm max-w-none p-6 text-text-primary">
					{@html renderData?.html ?? '<p>No content</p>'}
				</div>
			{:else if isXlsx}
				<!-- XLSX interactive table with sheet tabs -->
				<div class="flex h-full flex-col">
					{#if sheetNames.length > 1}
						<div class="flex gap-0.5 overflow-x-auto border-b border-border bg-surface-secondary px-3 pt-2">
							{#each sheetNames as name, i}
								<button
									type="button"
									class="shrink-0 rounded-t-lg px-3 py-1.5 text-xs font-medium transition-colors {
										i === activeSheet
											? 'bg-surface text-text-primary border border-border border-b-surface -mb-px'
											: 'text-text-secondary hover:text-text-primary hover:bg-surface/50'
									}"
									onclick={() => { activeSheet = i; }}
								>
									{name}
								</button>
							{/each}
						</div>
					{/if}
					<div class="flex-1 overflow-auto">
						<table class="w-full border-collapse text-xs">
							{#if currentSheetRows.length > 0}
								<thead>
									<tr>
										{#each currentSheetRows[0] as cell}
											<th class="sticky top-0 border border-border bg-surface-secondary px-3 py-2 text-left font-semibold text-text-primary">
												{cell ?? ''}
											</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each currentSheetRows.slice(1) as row, ri}
										<tr class="{ri % 2 === 0 ? 'bg-surface' : 'bg-surface-secondary/50'}">
											{#each row as cell}
												<td class="border border-border px-3 py-1.5 text-text-primary">
													{cell ?? ''}
												</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							{/if}
						</table>
					</div>
				</div>
			{:else if isPptx}
				<!-- PPTX slide carousel -->
				<div class="flex h-full flex-col">
					<div class="flex flex-1 items-center justify-center overflow-auto bg-surface-secondary p-6">
						{#if slides.length > 0}
							<div class="prose prose-sm max-w-3xl">
								{@html slides[activeSlide]?.html ?? '<p>No content</p>'}
							</div>
						{:else}
							<p class="text-sm text-text-secondary">No slides available</p>
						{/if}
					</div>
					{#if totalSlides > 1}
						<div class="flex items-center justify-center gap-4 border-t border-border px-4 py-3">
							<button
								type="button"
								class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
								disabled={activeSlide === 0}
								onclick={prevSlide}
								title="Previous slide"
							>
								<ChevronLeft size={18} />
							</button>
							<span class="text-xs font-medium text-text-secondary">
								{activeSlide + 1} / {totalSlides}
							</span>
							<button
								type="button"
								class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
								disabled={activeSlide === totalSlides - 1}
								onclick={nextSlide}
								title="Next slide"
							>
								<ChevronRight size={18} />
							</button>
						</div>
					{/if}
				</div>
			{:else if isText}
				<!-- Plain text / JSON -->
				<pre class="h-full overflow-auto p-6 text-xs leading-relaxed text-text-primary font-mono">{renderData?.text ?? ''}</pre>
			{:else}
				<!-- Unsupported type fallback -->
				<div class="flex h-full items-center justify-center">
					<div class="flex flex-col items-center gap-3 text-center">
						<p class="text-sm text-text-secondary">
							Preview not available for this file type.
						</p>
						<a
							href="/api/files/{fileId}/download"
							download
							class="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90"
						>
							<Download size={14} />
							Download file
						</a>
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>
