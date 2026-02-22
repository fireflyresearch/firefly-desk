/**
 * Sidebar state management.
 *
 * Persists sidebar open/closed state to localStorage so it survives
 * page reloads.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable } from 'svelte/store';

const STORAGE_KEY = 'firefly_sidebar_open';

function getInitialState(): boolean {
	if (typeof localStorage === 'undefined') return true;
	const stored = localStorage.getItem(STORAGE_KEY);
	if (stored === null) return true;
	return stored === 'true';
}

export const sidebarOpen = writable<boolean>(getInitialState());

// Persist changes to localStorage
sidebarOpen.subscribe((value) => {
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem(STORAGE_KEY, String(value));
	}
});

/** Toggle the sidebar open/closed state. */
export function toggleSidebar(): void {
	sidebarOpen.update((open) => !open);
}
