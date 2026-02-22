<!--
  ChatContainer.svelte - Main chat view combining messages and input.

  Renders the message list with auto-scroll, streaming indicators, and
  the InputBar. Handles the sendMessage flow. On first run, automatically
  initiates the setup conversation with Ember.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import MessageBubble from './MessageBubble.svelte';
	import StreamingMessage from './StreamingMessage.svelte';
	import InputBar from './InputBar.svelte';
	import ChatEmptyState from './ChatEmptyState.svelte';
	import {
		messages,
		activeConversationId,
		isStreaming
	} from '$lib/stores/chat.js';
	import { sendMessage, checkFirstRun } from '$lib/services/chat.js';

	let scrollContainer: HTMLDivElement | undefined = $state();
	let checkingFirstRun = $state(true);

	// Auto-scroll to bottom when messages change
	$effect(() => {
		// Subscribe to messages to trigger on changes
		const _ = $messages;
		scrollToBottom();
	});

	// Check first-run on mount
	$effect(() => {
		(async () => {
			try {
				const isFirstRun = await checkFirstRun();
				if (isFirstRun) {
					const conversationId = crypto.randomUUID();
					$activeConversationId = conversationId;
					await sendMessage(conversationId, '__setup_init__');
				}
			} catch {
				// Non-fatal -- continue with normal chat
			} finally {
				checkingFirstRun = false;
			}
		})();
	});

	function scrollToBottom() {
		// Use requestAnimationFrame to ensure DOM has updated
		requestAnimationFrame(() => {
			if (scrollContainer) {
				scrollContainer.scrollTop = scrollContainer.scrollHeight;
			}
		});
	}

	async function handleSend(text: string) {
		let conversationId = $activeConversationId;
		if (!conversationId) {
			conversationId = crypto.randomUUID();
			$activeConversationId = conversationId;
		}
		await sendMessage(conversationId, text);
	}

	let hasMessages = $derived($messages.length > 0);
</script>

<div class="flex h-full flex-col">
	<!-- Message list -->
	<div
		bind:this={scrollContainer}
		class="flex-1 overflow-y-auto"
	>
		{#if hasMessages}
			<div class="mx-auto flex max-w-3xl flex-col gap-1 py-4">
				{#each $messages as message (message.id)}
					{#if message.isStreaming}
						<StreamingMessage content={message.content} />
					{:else}
						<MessageBubble {message} />
					{/if}
				{/each}
			</div>
		{:else}
			<ChatEmptyState onSuggestionClick={handleSend} />
		{/if}
	</div>

	<!-- Gradient fade separator -->
	<div class="pointer-events-none h-6 bg-gradient-to-t from-surface to-transparent"></div>

	<!-- Input bar -->
	<InputBar onSend={handleSend} disabled={$isStreaming} />
</div>
