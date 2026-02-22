<!--
  ConversationList.svelte - Sidebar listing previous conversations.

  Reads from the conversations store and allows selecting or creating
  conversations.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, MessageSquare } from 'lucide-svelte';
	import {
		conversations,
		activeConversationId,
		clearMessages
	} from '$lib/stores/chat.js';

	function selectConversation(id: string) {
		$activeConversationId = id;
		clearMessages();
	}

	function newConversation() {
		$activeConversationId = null;
		clearMessages();
	}

	function truncate(text: string, maxLength: number): string {
		if (text.length <= maxLength) return text;
		return text.slice(0, maxLength) + '...';
	}
</script>

<div class="flex h-full flex-col border-r border-border bg-surface">
	<!-- Header with New Conversation button -->
	<div class="flex items-center justify-between border-b border-border px-3 py-3">
		<span class="text-xs font-semibold tracking-wide text-text-secondary uppercase">
			Conversations
		</span>
		<button
			type="button"
			onclick={newConversation}
			class="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
			aria-label="New conversation"
		>
			<Plus size={16} />
		</button>
	</div>

	<!-- Conversation items -->
	<div class="flex-1 overflow-y-auto">
		{#each $conversations as conversation (conversation.id)}
			{@const isActive = $activeConversationId === conversation.id}
			<button
				type="button"
				onclick={() => selectConversation(conversation.id)}
				class="flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition-colors
					{isActive ? 'bg-surface-hover' : 'hover:bg-surface-hover/50'}"
			>
				<span class="mt-0.5 shrink-0 text-text-secondary">
					<MessageSquare size={14} />
				</span>
				<div class="min-w-0 flex-1">
					<div class="truncate text-sm font-medium text-text-primary">
						{conversation.title}
					</div>
					<div class="mt-0.5 truncate text-xs text-text-secondary">
						{truncate(conversation.lastMessage, 60)}
					</div>
				</div>
			</button>
		{:else}
			<div class="px-3 py-6 text-center text-xs text-text-secondary">
				No conversations yet
			</div>
		{/each}
	</div>
</div>
