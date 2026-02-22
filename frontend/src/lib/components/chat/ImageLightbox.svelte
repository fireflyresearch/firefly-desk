<!--
  ImageLightbox.svelte - Modal overlay for full-size image viewing.

  Shows a centered image with dark backdrop, close button, download link,
  filename/alt text below, and escape key to close.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { fade } from 'svelte/transition';
	import { X, Download } from 'lucide-svelte';

	interface ImageLightboxProps {
		src: string;
		alt: string;
		onclose: () => void;
	}

	let { src, alt, onclose }: ImageLightboxProps = $props();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
	transition:fade={{ duration: 150 }}
	onclick={onclose}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') onclose(); }}
	role="dialog"
	aria-modal="true"
	aria-label="Image preview"
	tabindex="-1"
>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="relative flex flex-col items-center gap-3"
		onclick={(e) => { e.stopPropagation(); }}
		onkeydown={(e) => { e.stopPropagation(); }}
	>
		<img {src} {alt} class="max-w-[90vw] max-h-[85vh] object-contain rounded-lg shadow-2xl" />
		{#if alt}
			<p class="text-sm text-white/70">{alt}</p>
		{/if}
		<div class="absolute -top-2 -right-2 flex gap-1">
			<a
				href={src}
				download
				class="flex h-8 w-8 items-center justify-center rounded-full bg-surface-elevated/90 text-text-secondary hover:text-text-primary transition-colors"
				title="Download image"
				onclick={(e) => {
					e.stopPropagation();
				}}
			>
				<Download size={14} />
			</a>
			<button
				class="flex h-8 w-8 items-center justify-center rounded-full bg-surface-elevated/90 text-text-secondary hover:text-text-primary transition-colors"
				onclick={onclose}
				title="Close"
			>
				<X size={14} />
			</button>
		</div>
	</div>
</div>
