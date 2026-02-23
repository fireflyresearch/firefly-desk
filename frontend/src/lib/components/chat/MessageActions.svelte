<!--
  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->

<!--
  MessageActions.svelte - Floating action bar for assistant messages.

  Provides Copy, Regenerate, ThumbsUp, and ThumbsDown actions.
  Appears on hover over assistant messages via the parent group.
-->
<script lang="ts">
	import { Copy, RefreshCw, ThumbsUp, ThumbsDown, Check } from 'lucide-svelte';
	import { submitFeedback, regenerateLastMessage } from '$lib/services/chat.js';
	import { activeConversationId, isStreaming } from '$lib/stores/chat.js';
	import { get } from 'svelte/store';

	interface MessageActionsProps {
		messageId: string;
		content: string;
	}

	let { messageId, content }: MessageActionsProps = $props();

	let copied = $state(false);
	let feedbackGiven = $state<'up' | 'down' | null>(null);

	async function handleCopy() {
		try {
			await navigator.clipboard.writeText(content);
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		} catch {
			// Fallback for environments without clipboard API
			console.warn('[MessageActions] Clipboard API unavailable');
		}
	}

	async function handleRegenerate() {
		const conversationId = get(activeConversationId);
		if (!conversationId) return;
		if (get(isStreaming)) return;

		await regenerateLastMessage(conversationId);
	}

	async function handleFeedback(rating: 'up' | 'down') {
		if (feedbackGiven) return;
		feedbackGiven = rating;

		try {
			await submitFeedback(messageId, rating);
		} catch {
			console.error('[MessageActions] Failed to submit feedback');
			feedbackGiven = null;
		}
	}
</script>

<div
	class="flex items-center gap-0.5 rounded-lg border border-border bg-surface px-1 py-0.5 shadow-sm opacity-0 transition-opacity group-hover:opacity-100"
>
	<!-- Copy -->
	<button
		type="button"
		class="flex items-center justify-center rounded-md p-1.5 text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary"
		title={copied ? 'Copied!' : 'Copy to clipboard'}
		onclick={handleCopy}
	>
		{#if copied}
			<Check size={14} class="text-green-500" />
		{:else}
			<Copy size={14} />
		{/if}
	</button>

	<!-- Regenerate -->
	<button
		type="button"
		class="flex items-center justify-center rounded-md p-1.5 text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed"
		title="Regenerate response"
		onclick={handleRegenerate}
		disabled={$isStreaming}
	>
		<RefreshCw size={14} />
	</button>

	<!-- Thumbs Up -->
	<button
		type="button"
		class="flex items-center justify-center rounded-md p-1.5 transition-colors disabled:cursor-default
			{feedbackGiven === 'up'
			? 'text-green-500'
			: 'text-text-secondary hover:bg-surface-secondary hover:text-text-primary'}"
		title="Good response"
		onclick={() => handleFeedback('up')}
		disabled={feedbackGiven !== null}
	>
		<ThumbsUp size={14} />
	</button>

	<!-- Thumbs Down -->
	<button
		type="button"
		class="flex items-center justify-center rounded-md p-1.5 transition-colors disabled:cursor-default
			{feedbackGiven === 'down'
			? 'text-red-500'
			: 'text-text-secondary hover:bg-surface-secondary hover:text-text-primary'}"
		title="Poor response"
		onclick={() => handleFeedback('down')}
		disabled={feedbackGiven !== null}
	>
		<ThumbsDown size={14} />
	</button>
</div>
