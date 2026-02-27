<script lang="ts">
	import type { Snippet } from 'svelte';

	interface ResizableSplitProps {
		defaultLeftPercent?: number;
		rightVisible?: boolean;
		children: Snippet;
		panel?: Snippet;
	}

	let {
		defaultLeftPercent = 60,
		rightVisible = false,
		children,
		panel
	}: ResizableSplitProps = $props();

	let containerEl: HTMLDivElement | undefined = $state();
	let leftPercent = $state(60);
	let isDragging = $state(false);

	// Sync leftPercent when defaultLeftPercent prop changes
	$effect(() => {
		leftPercent = defaultLeftPercent;
	});

	let dividerClass = $derived(
		isDragging
			? 'flex w-1 shrink-0 cursor-col-resize items-center justify-center bg-accent/30'
			: 'flex w-1 shrink-0 cursor-col-resize items-center justify-center bg-border hover:bg-accent/20'
	);

	const MIN_LEFT_PX = 300;
	const MIN_RIGHT_PX = 200;

	function onPointerDown(e: PointerEvent) {
		if (!containerEl) return;
		isDragging = true;
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		e.preventDefault();
	}

	function onPointerMove(e: PointerEvent) {
		if (!isDragging || !containerEl) return;
		const rect = containerEl.getBoundingClientRect();
		const totalWidth = rect.width;
		const x = e.clientX - rect.left;

		// Enforce minimum widths
		const minLeftPercent = (MIN_LEFT_PX / totalWidth) * 100;
		const maxLeftPercent = ((totalWidth - MIN_RIGHT_PX) / totalWidth) * 100;

		let newPercent = (x / totalWidth) * 100;
		newPercent = Math.max(minLeftPercent, Math.min(maxLeftPercent, newPercent));
		leftPercent = newPercent;
	}

	function onPointerUp() {
		isDragging = false;
	}
</script>

<div
	class="relative flex min-h-0 flex-1"
	bind:this={containerEl}
>
	<!-- Left panel (chat) -->
	<div
		class="h-full min-h-0 overflow-auto"
		style:width={rightVisible ? `${leftPercent}%` : '100%'}
		style:transition={isDragging ? 'none' : 'width 0.15s ease'}
	>
		{@render children()}
	</div>

	{#if rightVisible && panel}
		<!-- Divider -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class={dividerClass}
			onpointerdown={onPointerDown}
			onpointermove={onPointerMove}
			onpointerup={onPointerUp}
			role="separator"
			aria-orientation="vertical"
			aria-label="Resize panels"
			tabindex={0}
		></div>

		<!-- Right panel (detail) -->
		<div
			class="min-h-0 flex-1 overflow-auto"
			style:transition={isDragging ? 'none' : 'width 0.15s ease'}
		>
			{@render panel()}
		</div>
	{/if}
</div>
