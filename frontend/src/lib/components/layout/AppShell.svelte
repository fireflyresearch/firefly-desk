<script lang="ts">
	import type { Snippet } from 'svelte';
	import TopBar from './TopBar.svelte';
	import ResizableSplit from './ResizableSplit.svelte';

	interface AppShellProps {
		title?: string;
		userName?: string;
		panelVisible?: boolean;
		children: Snippet;
		panel?: Snippet;
	}

	let {
		title = 'Firefly Desk',
		userName = 'User',
		panelVisible = false,
		children,
		panel
	}: AppShellProps = $props();
</script>

<div class="flex h-screen flex-col bg-surface">
	<TopBar {title} {userName} />

	<ResizableSplit rightVisible={panelVisible} {panel}>
		{@render children()}
	</ResizableSplit>
</div>
