<!--
  ThinkingIndicator.svelte - Ember pulse dot with context-aware status messages.

  Shows a pulsing ember dot and context-aware status messages while the
  agent is thinking. Tracks elapsed time and transitions through three phases:
  Phase 1 (0-3s): Analyzing messages
  Phase 2 (3-8s): Tool-specific or generic thinking messages
  Phase 3 (8s+): Patience messages

  Subscribes to activeTools for context-aware tool messages.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { activeTools } from '$lib/stores/tools.js';

	// Phase 1: Initial analyzing messages (0-3s)
	const analyzingMessages = [
		'Analyzing your request...',
		'Understanding the context...',
		'Processing your question...'
	];

	// Phase 2: Generic thinking messages (3-8s)
	const thinkingMessages = [
		'Consulting the knowledge graph...',
		'Connecting the dots...',
		'Cross-referencing documents...',
		'Assembling the puzzle pieces...',
		'Checking my references...',
		'Thinking deeply about this...'
	];

	// Phase 2: Tool-specific messages (3-8s)
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
		],
		save_memory: [
			'Saving to memory...',
			'Remembering this for later...',
			'Storing information...'
		],
		recall_memories: [
			'Recalling memories...',
			'Searching past conversations...',
			'Looking up what I remember...'
		],
		web_search: [
			'Searching the web...',
			'Looking up information online...',
			'Querying search results...'
		]
	};

	// Phase 3: Patience messages (8s+)
	const patienceMessages = [
		'This is taking a moment...',
		'Still working on it...',
		'Almost there, hang tight...',
		'Crunching through a lot of data...',
		'Working through a complex problem...'
	];

	let messageIndex = $state(0);
	let elapsedSeconds = $state(0);
	let currentActiveTools: { id: string; toolName: string }[] = $state([]);
	let displayedMessage = $state('');
	let messageVisible = $state(true);

	// Subscribe to activeTools
	$effect(() => {
		const unsubscribe = activeTools.subscribe((tools) => {
			currentActiveTools = tools;
		});
		return () => unsubscribe();
	});

	// Track elapsed time (updates every 100ms for smooth counting)
	$effect(() => {
		const id = setInterval(() => {
			elapsedSeconds += 0.1;
		}, 100);
		return () => clearInterval(id);
	});

	// Rotate messages based on phase
	$effect(() => {
		const id = setInterval(() => {
			// Fade out, update message, fade in
			messageVisible = false;
			setTimeout(() => {
				messageIndex++;
				messageVisible = true;
			}, 200);
		}, 2500);
		return () => clearInterval(id);
	});

	function getPhase(): 'analyzing' | 'thinking' | 'patience' {
		if (elapsedSeconds < 3) return 'analyzing';
		if (elapsedSeconds < 8) return 'thinking';
		return 'patience';
	}

	function getStatusMessage(): string {
		const phase = getPhase();

		if (phase === 'analyzing') {
			return analyzingMessages[messageIndex % analyzingMessages.length];
		}

		if (phase === 'thinking') {
			// If we have an active tool with specific messages, prefer those
			if (currentActiveTools.length > 0) {
				const activeTool = currentActiveTools[currentActiveTools.length - 1];
				const toolSpecificMessages = toolMessages[activeTool.toolName];
				if (toolSpecificMessages) {
					return toolSpecificMessages[messageIndex % toolSpecificMessages.length];
				}
			}
			return thinkingMessages[messageIndex % thinkingMessages.length];
		}

		// patience phase
		return patienceMessages[messageIndex % patienceMessages.length];
	}

	// Use $derived to recompute when dependencies change
	let statusMessage = $derived(getStatusMessage());

	// Keep displayed message in sync (with fade animation timing)
	$effect(() => {
		displayedMessage = statusMessage;
	});
</script>

<div class="flex items-center gap-2.5">
	<!-- Ember pulse dot -->
	<div class="ember-pulse-dot h-3 w-3 rounded-full bg-ember"></div>
	<!-- Rotating status message -->
	<span
		class="message-text text-xs text-text-secondary italic"
		class:message-visible={messageVisible}
		class:message-hidden={!messageVisible}
	>
		{displayedMessage}
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

	.message-text {
		transition: opacity 0.2s ease-in-out;
	}

	.message-visible {
		opacity: 1;
	}

	.message-hidden {
		opacity: 0;
	}
</style>
