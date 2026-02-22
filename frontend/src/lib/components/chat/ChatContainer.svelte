<!--
  ChatContainer.svelte - Main chat view combining messages and input.

  Renders the message list with auto-scroll, streaming indicators, and
  the InputBar. Handles the sendMessage flow.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { MessageSquareText } from 'lucide-svelte';
	import MessageBubble from './MessageBubble.svelte';
	import StreamingMessage from './StreamingMessage.svelte';
	import InputBar from './InputBar.svelte';
	import {
		messages,
		activeConversationId,
		isStreaming
	} from '$lib/stores/chat.js';
	import { sendMessage } from '$lib/services/chat.js';

	let scrollContainer: HTMLDivElement | undefined = $state();

	// Auto-scroll to bottom when messages change
	$effect(() => {
		// Subscribe to messages to trigger on changes
		const _ = $messages;
		scrollToBottom();
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
			<div class="flex flex-col gap-1 py-4">
				{#each $messages as message (message.id)}
					{#if message.isStreaming}
						<StreamingMessage content={message.content} />
					{:else}
						<MessageBubble {message} />
					{/if}
				{/each}
			</div>
		{:else}
			<!-- Empty state -->
			<div class="flex h-full flex-col items-center justify-center gap-3">
				<span class="text-text-secondary/40">
					<MessageSquareText size={48} strokeWidth={1} />
				</span>
				<p class="text-sm text-text-secondary">
					Start a conversation
				</p>
			</div>
		{/if}
	</div>

	<!-- Input bar -->
	<InputBar onSend={handleSend} disabled={$isStreaming} />
</div>
