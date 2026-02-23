<!--
  ReasoningIndicator.svelte - Shows reasoning steps as the agent thinks.

  Displays a list of reasoning steps with status indicators while the agent
  is processing a request using a reasoning pattern (ReAct, PlanAndExecute, etc.).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface ReasoningStep {
		step_number: number;
		step_type: string;
		description: string;
		status: string;
	}

	let { steps = [] }: { steps: ReasoningStep[] } = $props();
</script>

{#if steps.length > 0}
	<div
		class="reasoning-indicator rounded-lg border border-border bg-surface-elevated/50 p-3 text-sm"
	>
		<div class="mb-2 flex items-center gap-1.5 font-medium text-muted">
			<svg
				class="h-4 w-4"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path
					d="M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5 7.4V20a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-2.6c2.9-1.1 5-4 5-7.4a8 8 0 0 0-8-8z"
				/>
				<path d="M10 22h4" />
			</svg>
			Reasoning
		</div>
		<div class="space-y-1">
			{#each steps as step}
				<div class="flex items-start gap-2 text-muted/80">
					<span class="mt-0.5 shrink-0">
						{#if step.status === 'completed'}
							<svg
								class="h-3.5 w-3.5 text-emerald-500"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2.5"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
						{:else if step.status === 'running'}
							<svg
								class="h-3.5 w-3.5 animate-spin text-ember"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2.5"
							>
								<path d="M21 12a9 9 0 1 1-6.219-8.56" />
							</svg>
						{:else}
							<svg
								class="h-3.5 w-3.5 text-muted/40"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<circle cx="12" cy="12" r="8" />
							</svg>
						{/if}
					</span>
					<span>{step.description}</span>
				</div>
			{/each}
		</div>
	</div>
{/if}
