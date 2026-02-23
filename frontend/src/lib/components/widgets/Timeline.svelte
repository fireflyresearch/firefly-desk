<!--
  Timeline.svelte - Vertical timeline of events with dots and optional status.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import StatusBadge from './StatusBadge.svelte';

	interface TimelineEvent {
		timestamp: string;
		title: string;
		description?: string;
		status?: string;
	}

	interface TimelineProps {
		events: TimelineEvent[];
	}

	let { events }: TimelineProps = $props();
</script>

<div class="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm">
	<div class="relative">
		{#each events as event, i}
			<div class="relative flex gap-3 {i < events.length - 1 ? 'pb-5' : ''}">
				<!-- Vertical connecting line -->
				{#if i < events.length - 1}
					<div class="absolute left-[5px] top-3 bottom-0 w-px bg-border"></div>
				{/if}

				<!-- Accent-colored dot -->
				<div class="relative mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2 border-ember bg-surface-elevated"></div>

				<!-- Content -->
				<div class="min-w-0 flex-1">
					<div class="flex items-start justify-between gap-2">
						<p class="text-sm font-medium text-text-primary">{event.title}</p>
						{#if event.status}
							<div class="shrink-0">
								<StatusBadge label={event.status} status="neutral" />
							</div>
						{/if}
					</div>
					{#if event.description}
						<p class="mt-0.5 text-xs text-text-secondary">{event.description}</p>
					{/if}
					<time class="mt-1 block text-xs text-text-secondary">{event.timestamp}</time>
				</div>
			</div>
		{/each}
	</div>
</div>
