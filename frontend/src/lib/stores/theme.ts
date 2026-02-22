/**
 * Theme stores for light/dark mode preference and resolution.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable, derived } from 'svelte/store';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'flydesk_theme';

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

/** User-chosen preference: explicit light/dark or follow the OS. */
export const themePreference = writable<ThemePreference>('system');

/** Current OS-level colour-scheme preference. */
export const systemTheme = writable<ResolvedTheme>('light');

/** The concrete theme that should be applied (never 'system'). */
export const resolvedTheme = derived(
	[themePreference, systemTheme],
	([$pref, $sys]) => ($pref === 'system' ? $sys : $pref) as ResolvedTheme
);

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

/** Persist a preference and update the store. */
export function setTheme(pref: ThemePreference): void {
	themePreference.set(pref);
	try {
		localStorage.setItem(STORAGE_KEY, pref);
	} catch {
		// localStorage may be unavailable (e.g. private browsing quota exceeded)
	}
}

/**
 * Initialise theme state from localStorage and OS media query.
 * Must be called once from the root layout on mount (browser only).
 */
export function initTheme(): void {
	// --- Read persisted preference ---
	let stored: ThemePreference = 'system';
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw === 'light' || raw === 'dark' || raw === 'system') {
			stored = raw;
		}
	} catch {
		// ignore
	}
	themePreference.set(stored);

	// --- Detect OS preference ---
	const mql = window.matchMedia('(prefers-color-scheme: dark)');
	systemTheme.set(mql.matches ? 'dark' : 'light');

	mql.addEventListener('change', (e) => {
		systemTheme.set(e.matches ? 'dark' : 'light');
	});

	// --- Apply the resolved theme to the document ---
	resolvedTheme.subscribe((theme) => {
		document.documentElement.dataset.theme = theme;
	});
}
