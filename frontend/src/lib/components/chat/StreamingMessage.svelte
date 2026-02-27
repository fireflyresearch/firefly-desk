<!--
  StreamingMessage.svelte - Shows the currently streaming assistant response.

  Displays the ThinkingIndicator when no text has arrived yet, and a
  blinking cursor at the end of text while content is streaming. Features
  a pulsing ember gradient left border during streaming and a smooth
  fade-in when first content arrives.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import ThinkingIndicator from './ThinkingIndicator.svelte';
	import MarkdownContent from './MarkdownContent.svelte';
	import EmberAvatar from './EmberAvatar.svelte';

	interface StreamingMessageProps {
		content: string;
	}

	let { content }: StreamingMessageProps = $props();

	// Strip raw widget directives so they don't flash during streaming.
	// Matches both complete blocks (:::widget{...}...:::) and incomplete
	// ones that are still being streamed (:::widget{...} without closing :::).
	const WIDGET_COMPLETE = /:::widget\{[^}]*\}[\s\S]*?:::/g;
	const WIDGET_PARTIAL = /:::widget\{[^}]*\}[\s\S]*$/;
	let cleanContent = $derived(
		content.replace(WIDGET_COMPLETE, '').replace(WIDGET_PARTIAL, '').trim()
	);
	let hasContent = $derived(cleanContent.length > 0);
</script>

<div class="flex w-full justify-start px-4 py-1" transition:fly={{ y: 10, duration: 200 }}>
	<div class="flex gap-3">
		<!-- Ember avatar -->
		<div class="mt-1 flex h-7 w-7 shrink-0 items-center justify-center">
			<EmberAvatar size={20} />
		</div>
		<!-- Content area -->
		<div class="flex flex-col items-start">
			{#if hasContent}
				<div
					class="streaming-border border-l-2 pl-3 text-sm leading-relaxed"
					in:fade={{ duration: 300 }}
				>
					<MarkdownContent content={cleanContent} /><span
						class="streaming-cursor ml-0.5 inline-block h-4 w-[1.5px] translate-y-0.5 rounded-full bg-ember"
					></span>
				</div>
			{:else}
				<ThinkingIndicator />
			{/if}
		</div>
	</div>
</div>

<style>
	@keyframes blink {
		0%,
		100% {
			opacity: 1;
		}
		40% {
			opacity: 0;
		}
	}

	.streaming-cursor {
		animation: blink 1.1s ease-in-out infinite;
	}

	@keyframes ember-border-pulse {
		0%,
		100% {
			border-left-color: var(--color-ember, #f59e0b);
			box-shadow: -2px 0 8px -2px rgba(245, 158, 11, 0.3);
		}
		50% {
			border-left-color: rgba(245, 158, 11, 0.5);
			box-shadow: -2px 0 4px -2px rgba(245, 158, 11, 0.1);
		}
	}

	.streaming-border {
		border-left-color: var(--color-ember, #f59e0b);
		animation: ember-border-pulse 2s ease-in-out infinite;
	}
</style>
