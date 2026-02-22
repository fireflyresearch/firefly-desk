<!--
  ConfirmationCard.svelte - Safety confirmation card for high-risk tool operations.

  Renders a risk-level badge (yellow for HIGH_WRITE, red for DESTRUCTIVE),
  tool name, description, parameter summary, approve/reject buttons, and a
  countdown timer showing time remaining before the confirmation expires.

  When the user clicks Approve or Reject, the component sends a
  `__confirm__:<id>` or `__reject__:<id>` message via the chat service.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ShieldAlert, ShieldX, Clock, Check, X } from 'lucide-svelte';
	import { sendMessage } from '$lib/services/chat.js';
	import { activeConversationId } from '$lib/stores/chat.js';
	import { get } from 'svelte/store';

	type RiskLevel = 'high_write' | 'destructive';

	interface ConfirmationCardProps {
		confirmation_id: string;
		tool_name: string;
		tool_call_id?: string;
		risk_level: RiskLevel;
		message?: string;
		parameters?: Record<string, unknown>;
		description?: string;
		expires_at?: number;
	}

	let {
		confirmation_id,
		tool_name,
		tool_call_id,
		risk_level,
		message,
		parameters,
		description,
		expires_at
	}: ConfirmationCardProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let resolved: 'approved' | 'rejected' | null = $state(null);
	let timeRemaining = $state('');
	let isExpired = $state(false);

	// -----------------------------------------------------------------------
	// Risk-level styling
	// -----------------------------------------------------------------------

	const riskConfig: Record<RiskLevel, { label: string; badge: string; border: string; icon: typeof ShieldAlert }> = {
		high_write: {
			label: 'HIGH WRITE',
			badge: 'bg-warning/15 text-warning border-warning/30',
			border: 'border-l-warning',
			icon: ShieldAlert
		},
		destructive: {
			label: 'DESTRUCTIVE',
			badge: 'bg-danger/15 text-danger border-danger/30',
			border: 'border-l-danger',
			icon: ShieldX
		}
	};

	let config = $derived(riskConfig[risk_level] ?? riskConfig.high_write);
	let RiskIcon = $derived(config.icon);

	// -----------------------------------------------------------------------
	// Parameter summary
	// -----------------------------------------------------------------------

	let paramEntries = $derived(
		parameters ? Object.entries(parameters).filter(([, v]) => v != null) : []
	);

	function formatValue(value: unknown): string {
		if (typeof value === 'string') return value;
		if (typeof value === 'number' || typeof value === 'boolean') return String(value);
		return JSON.stringify(value);
	}

	// -----------------------------------------------------------------------
	// Countdown timer
	// -----------------------------------------------------------------------

	$effect(() => {
		if (expires_at == null || resolved != null) {
			timeRemaining = '';
			return;
		}

		function tick() {
			const now = Date.now() / 1000;
			const remaining = expires_at! - now;

			if (remaining <= 0) {
				isExpired = true;
				timeRemaining = 'Expired';
				return;
			}

			const minutes = Math.floor(remaining / 60);
			const seconds = Math.floor(remaining % 60);
			timeRemaining = `${minutes}:${seconds.toString().padStart(2, '0')}`;
		}

		tick();
		const interval = setInterval(tick, 1000);

		return () => clearInterval(interval);
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	async function handleApprove() {
		if (resolved || isExpired) return;
		resolved = 'approved';

		const conversationId = get(activeConversationId);
		if (conversationId) {
			await sendMessage(conversationId, `__confirm__:${confirmation_id}`);
		}
	}

	async function handleReject() {
		if (resolved || isExpired) return;
		resolved = 'rejected';

		const conversationId = get(activeConversationId);
		if (conversationId) {
			await sendMessage(conversationId, `__reject__:${confirmation_id}`);
		}
	}
</script>

<div
	class="rounded-xl border border-border border-l-4 {config.border} bg-surface-elevated p-5 shadow-sm"
>
	<!-- Header: icon + tool name + risk badge -->
	<div class="flex items-start justify-between gap-3">
		<div class="flex items-center gap-2.5 min-w-0">
			<span class="shrink-0 {risk_level === 'destructive' ? 'text-danger' : 'text-warning'}">
				<RiskIcon size={18} />
			</span>
			<div class="min-w-0">
				<h3 class="truncate text-sm font-semibold text-text-primary">
					Confirmation Required
				</h3>
				<p class="mt-0.5 text-xs text-text-secondary">
					<code class="rounded bg-surface-hover px-1 py-0.5 font-mono text-xs">{tool_name}</code>
				</p>
			</div>
		</div>
		<span
			class="shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase {config.badge}"
		>
			{config.label}
		</span>
	</div>

	<!-- Description / message -->
	{#if description || message}
		<p class="mt-3 text-sm text-text-secondary">
			{description ?? message}
		</p>
	{/if}

	<!-- Parameter summary -->
	{#if paramEntries.length > 0}
		<div class="mt-3 rounded-lg border border-border bg-surface p-4">
			<p class="mb-2 text-xs font-medium uppercase tracking-wider text-text-secondary">
				Parameters
			</p>
			<dl class="space-y-1">
				{#each paramEntries as [key, value]}
					<div class="flex items-baseline gap-2 text-xs">
						<dt class="shrink-0 font-medium text-text-primary">{key}:</dt>
						<dd class="truncate text-text-secondary font-mono">{formatValue(value)}</dd>
					</div>
				{/each}
			</dl>
		</div>
	{/if}

	<!-- Timer + action buttons -->
	<div class="mt-4 flex items-center justify-between">
		<!-- Countdown timer -->
		<div class="flex items-center gap-1.5 text-xs text-text-secondary">
			{#if resolved === 'approved'}
				<Check size={14} class="text-success" />
				<span class="text-success font-medium">Approved</span>
			{:else if resolved === 'rejected'}
				<X size={14} class="text-danger" />
				<span class="text-danger font-medium">Rejected</span>
			{:else if isExpired}
				<Clock size={14} class="text-danger" />
				<span class="text-danger font-medium">Expired</span>
			{:else if timeRemaining}
				<Clock size={14} />
				<span>Expires in {timeRemaining}</span>
			{/if}
		</div>

		<!-- Buttons -->
		{#if resolved == null && !isExpired}
			<div class="flex items-center gap-2">
				<button
					type="button"
					onclick={handleReject}
					class="btn-hover inline-flex items-center gap-1.5 rounded-lg border border-danger/30 bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger transition-all hover:bg-danger/20"
				>
					<X size={14} />
					Reject
				</button>
				<button
					type="button"
					onclick={handleApprove}
					class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-success px-3 py-1.5 text-xs font-medium text-white transition-all hover:bg-success/90"
				>
					<Check size={14} />
					Approve
				</button>
			</div>
		{/if}
	</div>
</div>
