<!--
  ThinkingIndicator.svelte - Animated asterisk with rotating status messages.

  Shows a Claude Code-inspired asterisk animation cycling through asterisk
  counts and rotating humorous status messages while the agent is thinking.
  Subscribes to activeTools for context-aware tool messages.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import { activeTools } from '$lib/stores/tools.js';

	// Asterisk animation: cycles * -> ** -> *** -> ** -> *
	const asteriskFrames = [' * ', ' ** ', ' *** ', ' ** ', ' * '];
	let asteriskIndex = $state(0);

	const asteriskInterval = setInterval(() => {
		asteriskIndex = (asteriskIndex + 1) % asteriskFrames.length;
	}, 200);

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
	let currentActiveTools: { id: string; toolName: string }[] = [];

	const unsubscribe = activeTools.subscribe((tools) => {
		currentActiveTools = tools;
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

	const messageInterval = setInterval(() => {
		messageIndex = messageIndex + 1;
	}, 2500);

	onDestroy(() => {
		clearInterval(asteriskInterval);
		clearInterval(messageInterval);
		unsubscribe();
	});
</script>

<div class="flex flex-col items-start gap-1.5">
	<!-- Animated asterisk -->
	<span class="font-mono text-sm font-bold text-accent">
		{asteriskFrames[asteriskIndex]}
	</span>
	<!-- Rotating status message -->
	<span class="text-xs text-text-secondary italic transition-opacity duration-300">
		{statusMessage}
	</span>
</div>
