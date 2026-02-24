/**
 * Sidebar state management.
 *
 * Persists sidebar open/closed state to localStorage so it survives
 * page reloads.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

const STORAGE_KEY = 'firefly_sidebar_open';

function getInitialState(): boolean {
	if (!browser) return true;
	const stored = localStorage.getItem(STORAGE_KEY);
	if (stored === null) return true;
	return stored === 'true';
}

export const sidebarOpen = writable<boolean>(getInitialState());

// Persist changes to localStorage
sidebarOpen.subscribe((value) => {
	if (browser) {
		localStorage.setItem(STORAGE_KEY, String(value));
	}
});

/**
 * Effective sidebar visibility — tracks whether the user wants the sidebar open.
 * The sidebar always renders when open (even with 0 conversations) so users
 * can start a new conversation.
 */
export const effectiveSidebarOpen = derived(
	sidebarOpen,
	($sidebarOpen) => $sidebarOpen
);

/** Toggle the sidebar open/closed state. */
export function toggleSidebar(): void {
	sidebarOpen.update((open) => !open);
}
