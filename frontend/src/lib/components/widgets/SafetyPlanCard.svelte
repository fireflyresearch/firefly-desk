<!--
  SafetyPlanCard.svelte - Batch operation safety plan overview.

  Lists all operations in a batch with per-operation risk indicators,
  which operations need confirmation, and an overall batch risk assessment.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Shield, ShieldAlert, ShieldX, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-svelte';
	import type { Component } from 'svelte';

	type RiskLevel = 'read' | 'low_write' | 'high_write' | 'destructive';

	interface OperationEntry {
		tool_name: string;
		risk_level: RiskLevel;
		requires_confirmation: boolean;
		description?: string;
	}

	interface SafetyPlanCardProps {
		operations: OperationEntry[];
		title?: string;
		overall_risk?: RiskLevel;
	}

	let { operations, title, overall_risk }: SafetyPlanCardProps = $props();

	let expanded = $state(true);

	// -----------------------------------------------------------------------
	// Risk-level configuration
	// -----------------------------------------------------------------------

	const riskMeta: Record<RiskLevel, { label: string; color: string; bgColor: string; borderColor: string; icon: Component; order: number }> = {
		read: {
			label: 'READ',
			color: 'text-success',
			bgColor: 'bg-success/10 text-success border-success/20',
			borderColor: 'border-l-success',
			icon: ShieldCheck,
			order: 0
		},
		low_write: {
			label: 'LOW WRITE',
			color: 'text-accent',
			bgColor: 'bg-accent/10 text-accent border-accent/20',
			borderColor: 'border-l-accent',
			icon: Shield,
			order: 1
		},
		high_write: {
			label: 'HIGH WRITE',
			color: 'text-warning',
			bgColor: 'bg-warning/10 text-warning border-warning/20',
			borderColor: 'border-l-warning',
			icon: ShieldAlert,
			order: 2
		},
		destructive: {
			label: 'DESTRUCTIVE',
			color: 'text-danger',
			bgColor: 'bg-danger/10 text-danger border-danger/20',
			borderColor: 'border-l-danger',
			icon: ShieldX,
			order: 3
		}
	};

	// -----------------------------------------------------------------------
	// Derived computations
	// -----------------------------------------------------------------------

	let computedOverallRisk = $derived<RiskLevel>(() => {
		if (overall_risk) return overall_risk;
		if (!operations || operations.length === 0) return 'read';

		let maxOrder = 0;
		let maxRisk: RiskLevel = 'read';
		for (const op of operations) {
			const meta = riskMeta[op.risk_level];
			if (meta && meta.order > maxOrder) {
				maxOrder = meta.order;
				maxRisk = op.risk_level;
			}
		}
		return maxRisk;
	});

	let overallRiskResolved = $derived(computedOverallRisk());
	let overallConfig = $derived(riskMeta[overallRiskResolved] ?? riskMeta.read);
	let OverallIcon = $derived(overallConfig.icon);

	let confirmationCount = $derived(
		operations?.filter((op) => op.requires_confirmation).length ?? 0
	);

	let operationCount = $derived(operations?.length ?? 0);
</script>

<div class="rounded-xl border border-border border-l-4 {overallConfig.borderColor} bg-surface-elevated shadow-sm">
	<!-- Header: collapsible -->
	<button
		type="button"
		onclick={() => (expanded = !expanded)}
		class="flex w-full items-center justify-between gap-3 p-5 text-left transition-colors hover:bg-surface-hover rounded-t-xl"
	>
		<div class="flex items-center gap-2.5 min-w-0">
			<span class="{overallConfig.color} shrink-0">
				<OverallIcon size={18} />
			</span>
			<div class="min-w-0">
				<h3 class="truncate text-sm font-semibold text-text-primary">
					{title ?? 'Safety Plan'}
				</h3>
				<p class="mt-0.5 text-xs text-text-secondary">
					{operationCount} operation{operationCount !== 1 ? 's' : ''}
					{#if confirmationCount > 0}
						&middot; {confirmationCount} need{confirmationCount === 1 ? 's' : ''} confirmation
					{/if}
				</p>
			</div>
		</div>
		<div class="flex items-center gap-2 shrink-0">
			<!-- Overall risk badge -->
			<span
				class="rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase {overallConfig.bgColor}"
			>
				{overallConfig.label}
			</span>
			{#if expanded}
				<ChevronUp size={16} class="text-text-secondary" />
			{:else}
				<ChevronDown size={16} class="text-text-secondary" />
			{/if}
		</div>
	</button>

	<!-- Operation list -->
	{#if expanded && operations && operations.length > 0}
		<div class="border-t border-border">
			<ul class="divide-y divide-border">
				{#each operations as op, i}
					{@const meta = riskMeta[op.risk_level] ?? riskMeta.read}
					{@const OpIcon = meta.icon}
					<li class="flex items-center gap-3 px-5 py-3">
						<!-- Risk icon -->
						<span class="{meta.color} shrink-0">
							<OpIcon size={16} />
						</span>

						<!-- Tool name + description -->
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<code class="text-xs font-mono font-medium text-text-primary">{op.tool_name}</code>
								{#if op.requires_confirmation}
									<span class="rounded-full bg-warning/15 border border-warning/30 px-1.5 py-0 text-[10px] font-medium text-warning uppercase">
										needs approval
									</span>
								{/if}
							</div>
							{#if op.description}
								<p class="mt-0.5 text-xs text-text-secondary truncate">{op.description}</p>
							{/if}
						</div>

						<!-- Risk badge -->
						<span
							class="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase {meta.bgColor}"
						>
							{meta.label}
						</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>
