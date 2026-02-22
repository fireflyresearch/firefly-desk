<!--
  AlertBanner.svelte - Alert/notification banner with severity-based styling.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Info, AlertTriangle, CircleX, CheckCircle } from 'lucide-svelte';
	import type { Component } from 'svelte';

	interface AlertBannerProps {
		message: string;
		severity: 'info' | 'warning' | 'error' | 'success';
		title?: string;
	}

	let { message, severity, title }: AlertBannerProps = $props();

	const icons: Record<AlertBannerProps['severity'], Component> = {
		info: Info,
		warning: AlertTriangle,
		error: CircleX,
		success: CheckCircle
	};

	const borderColors: Record<AlertBannerProps['severity'], string> = {
		info: 'border-l-accent',
		warning: 'border-l-warning',
		error: 'border-l-danger',
		success: 'border-l-success'
	};

	const bgColors: Record<AlertBannerProps['severity'], string> = {
		info: 'bg-accent/5',
		warning: 'bg-warning/5',
		error: 'bg-danger/5',
		success: 'bg-success/5'
	};

	const iconColors: Record<AlertBannerProps['severity'], string> = {
		info: 'text-accent',
		warning: 'text-warning',
		error: 'text-danger',
		success: 'text-success'
	};

	let Icon = $derived(icons[severity]);
	let borderColor = $derived(borderColors[severity]);
	let bgColor = $derived(bgColors[severity]);
	let iconColor = $derived(iconColors[severity]);
</script>

<div
	class="w-full rounded-lg border border-border border-l-4 {borderColor} {bgColor} p-4"
>
	<div class="flex items-start gap-3">
		<span class="mt-0.5 shrink-0 {iconColor}">
			<Icon size={18} />
		</span>
		<div class="min-w-0">
			{#if title}
				<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
				<p class="mt-1 text-sm text-text-secondary">{message}</p>
			{:else}
				<p class="text-sm text-text-primary">{message}</p>
			{/if}
		</div>
	</div>
</div>
