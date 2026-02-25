<!--
  HelpGuidesPage.svelte - Help & Guides documentation viewer.

  Two-pane layout with a searchable sidebar of doc titles and a content
  area that renders selected documentation as sanitized Markdown.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { BookOpen, Search, Loader2, FileText, AlertCircle } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import MarkdownContent from '$lib/components/shared/MarkdownContent.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface HelpDoc {
		slug: string;
		title: string;
		description: string;
	}

	interface HelpDocFull extends HelpDoc {
		content: string;
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let docs = $state<HelpDoc[]>([]);
	let selectedDoc = $state<HelpDocFull | null>(null);
	let loading = $state(true);
	let loadingContent = $state(false);
	let error = $state('');
	let searchQuery = $state('');

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let filteredDocs = $derived(
		searchQuery
			? docs.filter(
					(d) =>
						d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
						d.description.toLowerCase().includes(searchQuery.toLowerCase())
				)
			: docs
	);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadDocs() {
		loading = true;
		error = '';
		try {
			docs = await apiJson<HelpDoc[]>('/help/docs');
			// Auto-select first doc if none selected
			if (docs.length > 0 && !selectedDoc) {
				await selectDoc(docs[0].slug);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load help documents';
		} finally {
			loading = false;
		}
	}

	async function selectDoc(slug: string) {
		// Skip if already selected
		if (selectedDoc?.slug === slug) return;

		loadingContent = true;
		error = '';
		try {
			selectedDoc = await apiJson<HelpDocFull>(`/help/docs/${slug}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load document';
			selectedDoc = null;
		} finally {
			loadingContent = false;
		}
	}

	$effect(() => {
		loadDocs();
	});
</script>

<div class="flex h-full flex-col gap-4 p-6">
	<!-- Header -->
	<div>
		<h1 class="text-lg font-semibold text-text-primary">Help & Guides</h1>
		<p class="text-sm text-text-secondary">
			Browse documentation and guides for the admin console
		</p>
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			<div class="flex items-center gap-2">
				<AlertCircle size={14} />
				{error}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<!-- Two-pane layout -->
		<div class="flex flex-1 overflow-hidden rounded-xl border border-border">
			<!-- Left sidebar -->
			<div
				class="flex w-64 shrink-0 flex-col border-r border-border bg-surface-secondary/50 rounded-l-xl"
			>
				<!-- Search -->
				<div class="border-b border-border p-3">
					<div class="relative">
						<Search
							size={14}
							class="absolute top-1/2 left-3 -translate-y-1/2 text-text-secondary"
						/>
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="Search guides..."
							class="w-full rounded-md border border-border bg-surface py-1.5 pr-3 pl-8 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</div>
				</div>

				<!-- Doc list -->
				<ul class="flex flex-1 flex-col overflow-y-auto">
					{#each filteredDocs as doc}
						<li>
							<button
								type="button"
								onclick={() => selectDoc(doc.slug)}
								class="flex w-full flex-col gap-0.5 px-3 py-2.5 text-left transition-colors
									{selectedDoc?.slug === doc.slug
									? 'border-l-2 border-accent bg-accent/10 text-accent'
									: 'border-l-2 border-transparent text-text-primary hover:bg-surface-hover'}"
							>
								<span
									class="flex items-center gap-2 text-sm font-medium
										{selectedDoc?.slug === doc.slug ? 'text-accent' : 'text-text-primary'}"
								>
									<FileText size={14} class="shrink-0" />
									<span class="truncate">{doc.title}</span>
								</span>
								<span class="truncate pl-[22px] text-xs text-text-secondary">
									{doc.description}
								</span>
							</button>
						</li>
					{:else}
						<li class="px-3 py-6 text-center text-xs text-text-secondary">
							{searchQuery ? 'No guides match your search.' : 'No guides available.'}
						</li>
					{/each}
				</ul>
			</div>

			<!-- Right content area -->
			<div class="flex flex-1 flex-col overflow-y-auto bg-surface rounded-r-xl">
				{#if loadingContent}
					<div class="flex flex-1 items-center justify-center">
						<Loader2 size={24} class="animate-spin text-text-secondary" />
					</div>
				{:else if selectedDoc}
					<div class="px-8 py-6" style="max-width: 52rem;">
						<MarkdownContent content={selectedDoc.content} />
					</div>
				{:else}
					<div class="flex flex-1 flex-col items-center justify-center gap-3 text-text-secondary">
						<BookOpen size={40} strokeWidth={1} class="text-text-secondary/40" />
						<p class="text-sm">Select a guide from the sidebar to get started</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
