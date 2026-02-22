<!--
  MessageBubble.svelte - Displays a single chat message (user or assistant).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import type { Message } from '$lib/stores/chat.js';

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

<div class="flex w-full {isUser ? 'justify-end' : 'justify-start'} px-4 py-1">
	<div class="flex max-w-[75%] flex-col {isUser ? 'items-end' : 'items-start'}">
		<div
			class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words {isUser
				? 'bg-accent text-white rounded-br-sm'
				: 'bg-surface-secondary text-text-primary rounded-bl-sm border border-border'}"
		>
			{message.content}
		</div>
		<span class="mt-1 px-1 text-xs text-text-secondary">
			{formattedTime}
		</span>
	</div>
</div>
