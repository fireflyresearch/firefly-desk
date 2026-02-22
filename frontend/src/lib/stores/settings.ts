/**
 * User settings store -- persists preferences to the backend.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable, get } from 'svelte/store';
import { apiJson } from '$lib/services/api.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserSettings {
	theme: string; // managed by theme store, displayed here
	agentVerbose: boolean;
	sidebarCollapsed: boolean;
	notificationsEnabled: boolean;
	defaultModelId: string | null;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULTS: UserSettings = {
	theme: 'system',
	agentVerbose: false,
	sidebarCollapsed: false,
	notificationsEnabled: true,
	defaultModelId: null
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const userSettings = writable<UserSettings>({ ...DEFAULTS });

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Merge a partial update into the current settings. */
export function updateSettings(partial: Partial<UserSettings>): void {
	userSettings.update((current) => ({ ...current, ...partial }));
}

/** Fetch user settings from the backend. */
export async function loadUserSettings(): Promise<void> {
	try {
		const raw = await apiJson<Record<string, unknown>>('/settings/user');
		userSettings.set({
			theme: (raw.theme as string) ?? DEFAULTS.theme,
			agentVerbose: (raw.agent_verbose as boolean) ?? DEFAULTS.agentVerbose,
			sidebarCollapsed: (raw.sidebar_collapsed as boolean) ?? DEFAULTS.sidebarCollapsed,
			notificationsEnabled:
				(raw.notifications_enabled as boolean) ?? DEFAULTS.notificationsEnabled,
			defaultModelId: (raw.default_model_id as string | null) ?? DEFAULTS.defaultModelId
		});
	} catch {
		// Use defaults on error
	}
}

/** Save current user settings to the backend. */
export async function saveUserSettings(): Promise<void> {
	const current = get(userSettings);
	await apiJson('/settings/user', {
		method: 'PUT',
		body: JSON.stringify({
			theme: current.theme,
			agent_verbose: current.agentVerbose,
			sidebar_collapsed: current.sidebarCollapsed,
			notifications_enabled: current.notificationsEnabled,
			default_model_id: current.defaultModelId,
			display_preferences: {}
		})
	});
}
