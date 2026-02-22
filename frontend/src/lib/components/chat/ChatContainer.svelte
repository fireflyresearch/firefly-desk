<!--
  ChatContainer.svelte - Main chat view combining messages and input.

  Renders the message list with auto-scroll, streaming indicators, and
  the InputBar. Handles the sendMessage flow. On first run, automatically
  initiates the setup conversation with Ember. Supports drag-and-drop
  file uploads.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import MessageBubble from './MessageBubble.svelte';
	import StreamingMessage from './StreamingMessage.svelte';
	import WidgetSlot from './WidgetSlot.svelte';
	import InputBar from './InputBar.svelte';
	import ChatEmptyState from './ChatEmptyState.svelte';
	import DropOverlay from './DropOverlay.svelte';
	import {
		messages,
		activeConversationId,
		isStreaming
	} from '$lib/stores/chat.js';
	import { sendMessage, checkFirstRun } from '$lib/services/chat.js';
	import type { UploadedFile } from '$lib/services/files.js';

	let scrollContainer: HTMLDivElement | undefined = $state();
	let checkingFirstRun = $state(true);
	let showDropOverlay = $state(false);
	let pendingFiles: File[] = $state([]);
	let dragCounter = $state(0);

	// Auto-scroll to bottom when messages change
	$effect(() => {
		// Subscribe to messages to trigger on changes
		const _ = $messages;
		scrollToBottom();
	});

	// Check first-run on mount (with retry for slow backend startup)
	$effect(() => {
		(async () => {
			try {
				let isFirstRun = await checkFirstRun();
				// If first check returns false, wait and try once more
				// (backend may still be initializing)
				if (!isFirstRun) {
					await new Promise((r) => setTimeout(r, 1500));
					isFirstRun = await checkFirstRun();
				}
				if (isFirstRun) {
					console.log('[Setup] First run detected, starting setup wizard');
					const conversationId = crypto.randomUUID();
					$activeConversationId = conversationId;
					await sendMessage(conversationId, '__setup_init__');
				}
			} catch (error) {
				console.error('[Setup] Setup wizard failed:', error);
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

	async function handleSend(text: string, files?: UploadedFile[]) {
		let conversationId = $activeConversationId;
		if (!conversationId) {
			conversationId = crypto.randomUUID();
			$activeConversationId = conversationId;
		}

		const fileIds = files?.map((f) => f.id);
		const fileMeta = files?.map((f) => ({
			id: f.id,
			filename: f.filename,
			content_type: f.content_type,
			file_size: f.file_size
		}));

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

	<!-- Gradient fade separator -->
	<div class="pointer-events-none h-6 bg-gradient-to-t from-surface to-transparent"></div>

	<!-- Input bar -->
	<InputBar onSend={handleSend} disabled={$isStreaming} bind:pendingFiles conversationId={$activeConversationId} />
</div>
