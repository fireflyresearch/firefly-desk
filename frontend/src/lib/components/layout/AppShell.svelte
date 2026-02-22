<script lang="ts">
	import type { Snippet } from 'svelte';
	import { slide } from 'svelte/transition';
	import TopBar from './TopBar.svelte';
	import ResizableSplit from './ResizableSplit.svelte';
	import ConversationList from '../chat/ConversationList.svelte';
	import { sidebarOpen, toggleSidebar } from '$lib/stores/sidebar.js';

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
	<TopBar {title} {userName} onToggleSidebar={toggleSidebar} sidebarOpen={$sidebarOpen} />

	<div class="flex min-h-0 flex-1">
		{#if $sidebarOpen}
			<div
				transition:slide={{ axis: 'x', duration: 200 }}
				class="w-72 shrink-0 border-r border-border/50 bg-surface-secondary"
			>
				<ConversationList />
			</div>
		{/if}

		<ResizableSplit rightVisible={panelVisible} {panel}>
			{@render children()}
		</ResizableSplit>
	</div>
</div>
