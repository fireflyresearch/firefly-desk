<!--
  StreamingMessage.svelte - Shows the currently streaming assistant response.

  Displays a blinking cursor at the end of text and a "Thinking..." indicator
  when no text has arrived yet.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface StreamingMessageProps {
		content: string;
	}

	let { content }: StreamingMessageProps = $props();

	let hasContent = $derived(content.length > 0);
</script>

<div class="flex w-full justify-start px-4 py-1">
	<div class="flex max-w-[75%] flex-col items-start">
		<div
			class="rounded-2xl rounded-bl-sm border border-border bg-surface-secondary px-4 py-2.5 text-sm leading-relaxed text-text-primary"
		>
			{#if hasContent}
				<span class="whitespace-pre-wrap break-words">{content}</span><span
					class="streaming-cursor ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 bg-text-primary"
				></span>
			{:else}
				<span class="streaming-thinking text-text-secondary">Thinking...</span>
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

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}

	.streaming-cursor {
		animation: blink 1s step-end infinite;
	}

	.streaming-thinking {
		animation: pulse 2s ease-in-out infinite;
	}
</style>
