<!--
  ConfirmationCard.svelte - Confirmation dialog for high-risk operations.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { AlertTriangle } from 'lucide-svelte';

	interface ConfirmationCardProps {
		title: string;
		description: string;
		changes?: string[];
		action?: string;
		onConfirm?: () => void;
		onCancel?: () => void;
	}

	let { title, description, changes, action, onConfirm, onCancel }: ConfirmationCardProps =
		$props();
</script>

<div class="rounded-lg border border-border border-l-4 border-l-warning bg-surface p-4">
	<!-- Header -->
	<div class="flex items-start gap-3">
		<span class="mt-0.5 shrink-0 text-warning">
			<AlertTriangle size={18} />
		</span>
		<div class="min-w-0">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
			<p class="mt-1 text-sm text-text-secondary">{description}</p>
		</div>
	</div>

	<!-- Changes list -->
	{#if changes && changes.length > 0}
		<ul class="mt-3 ml-8 space-y-1">
			{#each changes as change}
				<li class="text-sm text-text-primary before:mr-2 before:text-text-secondary before:content-['\2022']">
					{change}
				</li>
			{/each}
		</ul>
	{/if}

	<!-- Actions -->
	<div class="mt-4 ml-8 flex items-center gap-2">
		<button
			type="button"
			onclick={onConfirm}
			class="rounded-md bg-warning px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-warning/90"
		>
			{action ?? 'Confirm'}
		</button>
		<button
			type="button"
			onclick={onCancel}
			class="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			Cancel
		</button>
	</div>
</div>
