<!--
  FeedbackDialog.svelte - Structured feedback dialog for thumbs-down.

  Shows category checkboxes and optional comment textarea.
  Compact, non-intrusive design. Uses Svelte 5 runes.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { X } from 'lucide-svelte';

	interface FeedbackDialogProps {
		onSubmit: (categories: string[], comment: string) => void;
		onCancel: () => void;
	}

	let { onSubmit, onCancel }: FeedbackDialogProps = $props();

	const CATEGORIES = [
		{ value: 'incorrect', label: 'Incorrect', description: 'Factually wrong or inaccurate' },
		{ value: 'unhelpful', label: 'Unhelpful', description: "Didn't answer the question" },
		{ value: 'too_verbose', label: 'Too verbose', description: 'Response was too long' },
		{ value: 'too_brief', label: 'Too brief', description: 'Not enough detail' },
		{ value: 'off_topic', label: 'Off-topic', description: "Didn't address the query" },
		{ value: 'tone_issue', label: 'Tone issue', description: 'Tone was inappropriate' },
		{ value: 'formatting', label: 'Formatting', description: 'Poor formatting or structure' },
	];

	let selectedCategories = $state<Set<string>>(new Set());
	let comment = $state('');

	function toggleCategory(value: string) {
		const next = new Set(selectedCategories);
		if (next.has(value)) next.delete(value);
		else next.add(value);
		selectedCategories = next;
	}

	function handleSubmit() {
		onSubmit([...selectedCategories], comment.trim());
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onCancel();
	}
</script>

<!-- Backdrop -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm"
	onclick={onCancel}
	onkeydown={handleKeydown}
>
	<!-- Dialog -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="w-full max-w-sm rounded-2xl border border-border bg-surface p-5 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
		onkeydown={handleKeydown}
	>
		<!-- Header -->
		<div class="mb-4 flex items-center justify-between">
			<h3 class="text-sm font-semibold text-text-primary">What went wrong?</h3>
			<button
				type="button"
				onclick={onCancel}
				class="flex h-6 w-6 items-center justify-center rounded-md text-text-secondary hover:bg-surface-hover"
				aria-label="Close"
			>
				<X size={14} />
			</button>
		</div>

		<!-- Categories -->
		<div class="mb-4 flex flex-wrap gap-2">
			{#each CATEGORIES as cat (cat.value)}
				<button
					type="button"
					onclick={() => toggleCategory(cat.value)}
					class="rounded-full border px-3 py-1 text-xs transition-colors
						{selectedCategories.has(cat.value)
						? 'border-accent bg-accent/10 text-accent font-medium'
						: 'border-border text-text-secondary hover:border-accent/50 hover:text-text-primary'}"
					title={cat.description}
				>
					{cat.label}
				</button>
			{/each}
		</div>

		<!-- Comment -->
		<textarea
			bind:value={comment}
			placeholder="Additional details (optional)..."
			rows={3}
			class="mb-4 w-full resize-none rounded-lg border border-border bg-surface-secondary/50 px-3 py-2 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50"
		></textarea>

		<!-- Actions -->
		<div class="flex justify-end gap-2">
			<button
				type="button"
				onclick={onCancel}
				class="rounded-lg px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
			>
				Cancel
			</button>
			<button
				type="button"
				onclick={handleSubmit}
				class="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				Submit
			</button>
		</div>
	</div>
</div>
