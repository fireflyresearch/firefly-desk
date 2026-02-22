<!--
  ThinkingIndicator.svelte - Ember pulse dot with rotating status messages.

  Shows a pulsing ember dot and rotating humorous status messages while the
  agent is thinking. Subscribes to activeTools for context-aware tool messages.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { activeTools } from '$lib/stores/tools.js';

	// Rotating status messages
	const genericMessages = [
		'Warming up the neurons...',
		'Consulting the knowledge graph...',
		'Rummaging through the catalog...',
		'Connecting the dots...',
		'Parsing the universe...',
		'Checking my references...',
		'Thinking deeply about this...',
		'Cross-referencing documents...',
		'Assembling the puzzle pieces...',
		'Running diagnostics...'
	];

	const toolMessages: Record<string, string[]> = {
		knowledge_retrieval: [
			'Searching the knowledge base...',
			'Reading through relevant documents...',
			'Gathering knowledge snippets...'
		],
		catalog_search: [
			'Browsing the service catalog...',
			'Looking up registered systems...',
			'Scanning catalog entries...'
		],
		audit_lookup: [
			'Reviewing audit trails...',
			'Checking recent audit events...',
			'Inspecting the audit log...'
		]
	};

	let messageIndex = $state(0);
	let currentActiveTools: { id: string; toolName: string }[] = $state([]);

	// Subscribe to activeTools and rotate messages using $effect with cleanup
	$effect(() => {
		const unsubscribe = activeTools.subscribe((tools) => {
			currentActiveTools = tools;
		});
		return () => unsubscribe();
	});

	$effect(() => {
		const id = setInterval(() => {
			messageIndex++;
		}, 2500);
		return () => clearInterval(id);
	});

	function getStatusMessage(): string {
		// If we have an active tool with specific messages, prefer those
		if (currentActiveTools.length > 0) {
			const activeTool = currentActiveTools[currentActiveTools.length - 1];
			const toolSpecificMessages = toolMessages[activeTool.toolName];
			if (toolSpecificMessages) {
				return toolSpecificMessages[messageIndex % toolSpecificMessages.length];
			}
		}
		return genericMessages[messageIndex % genericMessages.length];
	}

	let statusMessage = $derived(getStatusMessage());
</script>

<div class="flex items-center gap-2.5">
	<!-- Ember pulse dot -->
	<div class="ember-pulse-dot h-3 w-3 rounded-full bg-ember"></div>
	<!-- Rotating status message -->
	<span class="text-xs text-text-secondary italic transition-opacity duration-300">
		{statusMessage}
	</span>
</div>

<style>
	@keyframes ember-pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4);
			opacity: 1;
		}
		50% {
			box-shadow: 0 0 12px 4px rgba(245, 158, 11, 0.15);
			opacity: 0.7;
		}
	}

	.ember-pulse-dot {
		animation: ember-pulse 1.5s ease-in-out infinite;
	}
</style>
