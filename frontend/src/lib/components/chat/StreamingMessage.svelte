<!--
  StreamingMessage.svelte - Shows the currently streaming assistant response.

  Displays the ThinkingIndicator when no text has arrived yet, and a
  blinking cursor at the end of text while content is streaming.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Bot } from 'lucide-svelte';
	import ThinkingIndicator from './ThinkingIndicator.svelte';
	import MarkdownContent from './MarkdownContent.svelte';

	interface StreamingMessageProps {
		content: string;
	}

	let { content }: StreamingMessageProps = $props();

	let hasContent = $derived(content.length > 0);
</script>

<div class="flex w-full justify-start px-4 py-1">
	<div class="flex gap-3">
		<!-- Bot avatar -->
		<div class="mt-1 shrink-0">
			<Bot size={20} class="text-accent" />
		</div>
		<!-- Content area -->
		<div class="flex flex-col items-start">
			{#if hasContent}
				<div class="text-sm leading-relaxed">
					<MarkdownContent content={content} /><span
						class="streaming-cursor ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 bg-text-primary"
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
		50% {
			opacity: 0;
		}
	}

	.streaming-cursor {
		animation: blink 1s step-end infinite;
	}
</style>
