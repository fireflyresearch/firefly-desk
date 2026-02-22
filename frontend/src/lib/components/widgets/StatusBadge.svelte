<!--
  StatusBadge.svelte - Small inline badge showing a status with colored dot.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface StatusBadgeProps {
		label: string;
		status: 'success' | 'warning' | 'error' | 'info' | 'neutral';
	}

	let { label, status }: StatusBadgeProps = $props();

	const dotColors: Record<StatusBadgeProps['status'], string> = {
		success: 'bg-success',
		warning: 'bg-warning',
		error: 'bg-danger',
		info: 'bg-accent',
		neutral: 'bg-text-secondary'
	};

	const bgColors: Record<StatusBadgeProps['status'], string> = {
		success: 'bg-success/10',
		warning: 'bg-warning/10',
		error: 'bg-danger/10',
		info: 'bg-accent/10',
		neutral: 'bg-text-secondary/10'
	};

	let dotColor = $derived(dotColors[status] ?? dotColors.neutral);
	let bgColor = $derived(bgColors[status] ?? bgColors.neutral);
</script>

<span
	class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium text-text-primary {bgColor}"
>
	<span class="h-1.5 w-1.5 rounded-full {dotColor}"></span>
	{label}
</span>
