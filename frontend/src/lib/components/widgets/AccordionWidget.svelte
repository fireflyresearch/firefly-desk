<!--
  AccordionWidget.svelte - Collapsible accordion sections.

  Renders a list of collapsible sections with animated expand/collapse.
  Multiple sections can be open simultaneously. Sections are toggled
  individually with a rotating chevron indicator.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ChevronRight } from 'lucide-svelte';

	interface AccordionSection {
		title: string;
		content: string;
	}

	interface AccordionWidgetProps {
		sections: AccordionSection[];
		defaultOpen?: number | number[];
	}

	let { sections, defaultOpen }: AccordionWidgetProps = $props();

	/** Resolve a defaultOpen value into a Set of indices. */
	function resolveDefaults(val: number | number[] | undefined): Set<number> {
		if (val == null) return new Set();
		if (Array.isArray(val)) return new Set(val);
		return new Set([val]);
	}

	// eslint-disable-next-line svelte/state-referenced-locally -- intentional one-time initialization
	let openSet = $state(resolveDefaults(defaultOpen));

	function toggle(index: number) {
		// Create a new Set so Svelte detects the mutation
		const next = new Set(openSet);
		if (next.has(index)) {
			next.delete(index);
		} else {
			next.add(index);
		}
		openSet = next;
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden divide-y divide-border">
	{#each sections as section, i}
		{@const isOpen = openSet.has(i)}
		<div>
			<!-- Section header (button) -->
			<button
				type="button"
				class="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left transition-colors hover:bg-surface-secondary/50"
				aria-expanded={isOpen}
				onclick={() => toggle(i)}
			>
				<span class="text-sm font-semibold text-text-primary">{section.title}</span>
				<span
					class="shrink-0 text-text-secondary transition-transform duration-200 {isOpen ? 'rotate-90' : ''}"
				>
					<ChevronRight size={16} />
				</span>
			</button>

			<!-- Collapsible content -->
			{#if isOpen}
				<div class="accordion-content px-5 pb-4">
					<p class="text-sm text-text-secondary leading-relaxed">{section.content}</p>
				</div>
			{/if}
		</div>
	{/each}
</div>

<style>
	.accordion-content {
		animation: accordion-open 0.2s ease-out;
	}

	@keyframes accordion-open {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
