<!--
  ActionButtons.svelte - Follow-up action chips for the chat.

  Renders a horizontal row of action buttons that send a predefined message
  to the active conversation when clicked. Supports 'default', 'primary',
  and 'outline' variants for visual differentiation.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Sparkles } from 'lucide-svelte';
	import { sendMessage } from '$lib/services/chat.js';
	import { activeConversationId } from '$lib/stores/chat.js';
	import { get } from 'svelte/store';

	type ActionVariant = 'default' | 'primary' | 'outline';

	interface Action {
		label: string;
		message: string;
		variant?: ActionVariant;
	}

	interface ActionButtonsProps {
		actions: Action[];
	}

	let { actions }: ActionButtonsProps = $props();

	let sentIndex: number | null = $state(null);

	const variantClasses: Record<ActionVariant, string> = {
		default:
			'border-border bg-surface-secondary text-text-primary hover:bg-surface-hover',
		primary:
			'border-accent/30 bg-accent/10 text-accent hover:bg-accent/20',
		outline:
			'border-border bg-transparent text-text-secondary hover:bg-surface-secondary hover:text-text-primary'
	};

	async function handleClick(action: Action, index: number) {
		if (sentIndex != null) return; // debounce
		sentIndex = index;

		const conversationId = get(activeConversationId);
		if (conversationId) {
			await sendMessage(conversationId, action.message);
		}
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm transition-shadow hover:shadow-md">
	<div class="flex flex-wrap items-center gap-2">
		{#each actions as action, i}
			{@const variant = action.variant ?? 'default'}
			<button
				type="button"
				class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all {sentIndex === i
					? 'border-success/30 bg-success/10 text-success cursor-default'
					: sentIndex != null
						? 'opacity-50 cursor-not-allowed ' + variantClasses[variant]
						: variantClasses[variant]}"
				disabled={sentIndex != null}
				onclick={() => handleClick(action, i)}
			>
				{#if sentIndex === i}
					<Sparkles size={12} />
				{/if}
				{action.label}
			</button>
		{/each}
	</div>
</div>
