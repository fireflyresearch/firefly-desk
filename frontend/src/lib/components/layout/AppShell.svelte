<script lang="ts">
	import type { Snippet } from 'svelte';
	import { slide } from 'svelte/transition';
	import { page } from '$app/stores';
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

	/** Hide the conversation sidebar on admin/settings pages (they have their own nav). */
	let isAdminPage = $derived($page.url.pathname.startsWith('/admin'));
	let isSettingsPage = $derived($page.url.pathname.startsWith('/settings'));
	let showSidebar = $derived($sidebarOpen && !isAdminPage && !isSettingsPage);
</script>

<div class="flex h-screen flex-col bg-surface">
	<TopBar
		{title}
		{userName}
		onToggleSidebar={isAdminPage || isSettingsPage ? undefined : toggleSidebar}
		sidebarOpen={showSidebar}
	/>

	<div class="flex min-h-0 flex-1">
		{#if showSidebar}
			<div
				transition:slide={{ axis: 'x', duration: 200 }}
				class="w-80 shrink-0 border-r border-border/50 bg-surface-secondary"
			>
				<ConversationList />
			</div>
		{/if}

		<ResizableSplit rightVisible={panelVisible} {panel}>
			{@render children()}
		</ResizableSplit>
	</div>
</div>
