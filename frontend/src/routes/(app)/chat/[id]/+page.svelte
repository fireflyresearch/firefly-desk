<!--
  Chat conversation page — loads a specific conversation by ID from the URL.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import ChatContainer from '$lib/components/chat/ChatContainer.svelte';
	import { selectConversation, activeConversationId } from '$lib/stores/chat.js';

	// Load the conversation when the route param changes
	$effect(() => {
		const id = $page.params.id;
		if (id && id !== $activeConversationId) {
			selectConversation(id);
		}
	});
</script>

<ChatContainer />
