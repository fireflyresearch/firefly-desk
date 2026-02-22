<!--
  MessageBubble.svelte - Displays a single chat message (user or assistant).

  User messages: right-aligned bubble with accent background.
  Assistant messages: full-width left-aligned with bot avatar and markdown rendering.
  Timestamps appear on hover for both message types.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Bot } from 'lucide-svelte';
	import type { Message } from '$lib/stores/chat.js';
	import MarkdownContent from './MarkdownContent.svelte';
	import ToolSummary from './ToolSummary.svelte';

	interface MessageBubbleProps {
		message: Message;
	}

	let { message }: MessageBubbleProps = $props();

	let formattedTime = $derived(
		message.timestamp.toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit'
		})
	);

	let isUser = $derived(message.role === 'user');
</script>

{#if isUser}
	<!-- User message: right-aligned bubble -->
	<div class="group flex w-full justify-end px-4 py-1">
		<div class="flex max-w-[75%] flex-col items-end">
			<div
				class="rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm whitespace-pre-wrap break-words"
			>
				{message.content}
			</div>
			<span
				class="mt-1 px-1 text-xs text-text-secondary opacity-0 transition-opacity group-hover:opacity-100"
			>
				{formattedTime}
			</span>
		</div>
	</div>
{:else}
	<!-- Assistant message: full-width left-aligned, no bubble background -->
	<div class="group flex w-full justify-start px-4 py-1">
		<div class="flex gap-3">
			<!-- Bot avatar -->
			<div class="mt-1 shrink-0">
				<Bot size={20} class="text-accent" />
			</div>
			<!-- Message content -->
			<div class="flex flex-col items-start">
				<div class="text-sm leading-relaxed">
					<MarkdownContent content={message.content} />
				</div>
				{#if !message.isStreaming && message.toolExecutions?.length}
					<ToolSummary tools={message.toolExecutions} />
				{/if}
				<span
					class="mt-1 px-1 text-xs text-text-secondary opacity-0 transition-opacity group-hover:opacity-100"
				>
					{formattedTime}
				</span>
			</div>
		</div>
	</div>
{/if}
