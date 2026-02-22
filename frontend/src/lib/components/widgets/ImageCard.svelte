<!--
  ImageCard.svelte - Widget for displaying images with optional caption.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import ImageLightbox from '$lib/components/chat/ImageLightbox.svelte';

	interface ImageCardProps {
		src: string;
		alt?: string;
		caption?: string;
	}

	let { src, alt = '', caption = '' }: ImageCardProps = $props();
	let showLightbox = $state(false);
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	<button type="button" class="block w-full" onclick={() => { showLightbox = true; }}>
		<img {src} {alt} class="w-full max-h-80 object-contain bg-surface cursor-pointer" />
	</button>
	{#if caption || alt}
		<div class="px-4 py-2.5 border-t border-border">
			<p class="text-sm text-text-secondary">{caption || alt}</p>
		</div>
	{/if}
</div>

{#if showLightbox}
	<ImageLightbox {src} alt={alt || caption || 'Image'} onclose={() => { showLightbox = false; }} />
{/if}
