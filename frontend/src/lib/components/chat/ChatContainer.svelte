<!--
  ChatContainer.svelte - Main chat view combining messages and input.

  Renders the message list with auto-scroll, streaming indicators, and
  the InputBar. Handles the sendMessage flow. Supports drag-and-drop
  file uploads. Features smooth scrolling and a floating "scroll to bottom"
  button when the user has scrolled up during streaming.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { fade } from 'svelte/transition';
	import { ArrowDown } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import MessageBubble from './MessageBubble.svelte';
	import StreamingMessage from './StreamingMessage.svelte';
	import ReasoningIndicator from './ReasoningIndicator.svelte';
	import WidgetSlot from './WidgetSlot.svelte';
	import InputBar from './InputBar.svelte';
	import ChatEmptyState from './ChatEmptyState.svelte';
	import DropOverlay from './DropOverlay.svelte';
	import {
		messages,
		activeConversationId,
		isStreaming,
		reasoningSteps,
		createNewConversation
	} from '$lib/stores/chat.js';
	import { sendMessage } from '$lib/services/chat.js';
	import type { UploadedFile } from '$lib/services/files.js';

	let scrollContainer: HTMLDivElement | undefined = $state();
	let showDropOverlay = $state(false);
	let pendingFiles: File[] = $state([]);
	let dragCounter = $state(0);
	let userScrolledUp = $state(false);

	// Threshold (in pixels) for considering the user "at the bottom"
	const SCROLL_THRESHOLD = 80;

	// Auto-scroll to bottom when messages change (only if user hasn't scrolled up)
	$effect(() => {
		// Subscribe to messages to trigger on changes
		const _ = $messages;
		if (!userScrolledUp) {
			scrollToBottom();
		}
	});

	function scrollToBottom() {
		// Use requestAnimationFrame to ensure DOM has updated
		requestAnimationFrame(() => {
			if (scrollContainer) {
				scrollContainer.scrollTo({
					top: scrollContainer.scrollHeight,
					behavior: 'smooth'
				});
				userScrolledUp = false;
			}
		});
	}

	function handleScroll() {
		if (!scrollContainer) return;
		const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
		const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
		userScrolledUp = distanceFromBottom > SCROLL_THRESHOLD;
	}

	let showScrollButton = $derived(userScrolledUp && $isStreaming);

	async function handleSend(text: string, files?: UploadedFile[]) {
		let conversationId = $activeConversationId;
		if (!conversationId) {
			conversationId = await createNewConversation();
			goto(`/chat/${conversationId}`);
		}

		const fileIds = files?.map((f) => f.id);
		const fileMeta = files?.map((f) => ({
			id: f.id,
			filename: f.filename,
			content_type: f.content_type,
			file_size: f.file_size
		}));

		// Scroll to bottom when sending a new message
		userScrolledUp = false;
		await sendMessage(conversationId, text, fileIds, fileMeta);
	}

	function handleDragEnter(e: DragEvent) {
		e.preventDefault();
		dragCounter++;
		if (e.dataTransfer?.types.includes('Files')) {
			showDropOverlay = true;
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
	}

	function handleDragLeave(e: DragEvent) {
		e.preventDefault();
		dragCounter--;
		if (dragCounter <= 0) {
			dragCounter = 0;
			showDropOverlay = false;
		}
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragCounter = 0;
		showDropOverlay = false;

		if (e.dataTransfer?.files) {
			const droppedFiles = Array.from(e.dataTransfer.files);
			if (droppedFiles.length > 0) {
				pendingFiles = [...pendingFiles, ...droppedFiles];
			}
		}
	}

	let hasMessages = $derived($messages.length > 0);
</script>

<div
	class="relative flex h-full flex-col"
	ondragenter={handleDragEnter}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	ondrop={handleDrop}
	role="region"
	aria-label="Chat area"
>
	{#if showDropOverlay}
		<DropOverlay />
	{/if}

	<!-- Message list -->
	<div
		bind:this={scrollContainer}
		class="flex-1 overflow-y-auto scroll-smooth"
		onscroll={handleScroll}
	>
		{#if hasMessages}
			<div class="mx-auto flex max-w-3xl flex-col gap-1 py-4">
				{#each $messages as message, index (message.id)}
					{#if message.isStreaming}
						{#if $reasoningSteps.length > 0}
							<div class="px-4 py-1">
								<div class="ml-10">
									<ReasoningIndicator steps={$reasoningSteps} />
								</div>
							</div>
						{/if}
						<StreamingMessage content={message.content} />
					{:else}
						<MessageBubble {message} {index} messageCount={$messages.length} />
					{/if}
					{#if message.widgets?.length}
						<div class="px-4 py-1">
							<div class="ml-10 flex flex-col gap-2">
								{#each message.widgets.filter((w) => w.display === 'inline') as widget (widget.widget_id)}
									<WidgetSlot directive={widget} />
								{/each}
							</div>
						</div>
					{/if}
				{/each}
			</div>
		{:else}
			<ChatEmptyState onSuggestionClick={handleSend} />
		{/if}
	</div>

	<!-- Scroll to bottom button -->
	{#if showScrollButton}
		<div class="absolute bottom-28 left-1/2 z-10 -translate-x-1/2" transition:fade={{ duration: 200 }}>
			<button
				type="button"
				class="flex items-center gap-1.5 rounded-full border border-border bg-surface-elevated px-3 py-1.5 text-xs font-medium text-text-secondary shadow-lg transition-colors hover:bg-surface-secondary hover:text-text-primary"
				onclick={scrollToBottom}
			>
				<ArrowDown size={14} />
				<span>Scroll to bottom</span>
			</button>
		</div>
	{/if}

	<!-- Gradient fade separator -->
	<div class="pointer-events-none h-6 bg-gradient-to-t from-surface to-transparent"></div>

	<!-- Input bar -->
	<InputBar onSend={handleSend} disabled={$isStreaming} bind:pendingFiles conversationId={$activeConversationId} />
</div>
