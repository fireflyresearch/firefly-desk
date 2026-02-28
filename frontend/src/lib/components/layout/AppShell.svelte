<script lang="ts">
	import type { Snippet } from 'svelte';
	import { fade, slide } from 'svelte/transition';
	import { PanelLeft, PanelLeftClose } from 'lucide-svelte';
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
	let canToggle = $derived(!isAdminPage && !isSettingsPage);
</script>

<div class="flex h-screen flex-col bg-surface">
	<TopBar {title} {userName} />

	<div class="relative flex min-h-0 flex-1">
		{#if showSidebar}
			<div
				transition:slide={{ axis: 'x', duration: 200 }}
				class="flex w-80 shrink-0 flex-col border-r border-border/50 bg-surface-secondary"
			>
				<!-- Sidebar collapse button -->
				<div class="flex items-center justify-end px-2 pt-2">
					<button
						type="button"
						onclick={toggleSidebar}
						class="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary/60 transition-colors hover:bg-surface-hover hover:text-text-primary"
						aria-label="Collapse sidebar"
					>
						<PanelLeftClose size={16} />
					</button>
				</div>
				<div class="min-h-0 flex-1">
					<ConversationList />
				</div>
			</div>
		{:else if canToggle}
			<!-- Floating expand button when sidebar is collapsed -->
			<div class="absolute left-2 top-2 z-10" transition:fade={{ duration: 150 }}>
				<button
					type="button"
					onclick={toggleSidebar}
					class="flex h-8 w-8 items-center justify-center rounded-lg border border-border/50 bg-surface-elevated text-text-secondary shadow-sm transition-colors hover:bg-surface-hover hover:text-text-primary"
					aria-label="Expand sidebar"
				>
					<PanelLeft size={16} />
				</button>
			</div>
		{/if}

		<ResizableSplit rightVisible={panelVisible} {panel}>
			{@render children()}
		</ResizableSplit>
	</div>
</div>
