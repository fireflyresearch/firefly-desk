<!--
  PanelHeader.svelte - Header bar for the right-side detail panel.

  Displays the current panel title, a back button when the stack has
  more than one item, a depth indicator, and a close button.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ChevronLeft, X } from 'lucide-svelte';

	interface PanelHeaderProps {
		title: string;
		depth: number;
		onBack: () => void;
		onClose: () => void;
	}

	let { title, depth, onBack, onClose }: PanelHeaderProps = $props();

	let depthLabel = $derived(depth > 1 ? `${depth} of ${depth}` : '');
</script>

<header
	class="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-surface px-3"
>
	<!-- Back button (only when stack depth > 1) -->
	{#if depth > 1}
		<button
			type="button"
			onclick={onBack}
			class="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			aria-label="Go back"
		>
			<ChevronLeft size={18} />
		</button>
	{/if}

	<!-- Title -->
	<h2 class="min-w-0 flex-1 truncate text-sm font-semibold text-text-primary">
		{title}
	</h2>

	<!-- Depth indicator -->
	{#if depthLabel}
		<span class="shrink-0 text-xs text-text-secondary">
			{depthLabel}
		</span>
	{/if}

	<!-- Close button -->
	<button
		type="button"
		onclick={onClose}
		class="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		aria-label="Close panel"
	>
		<X size={16} />
	</button>
</header>
