/**
 * Agent settings store -- caches the admin-managed agent personality,
 * avatar, greeting, and display name so that TopBar, MessageBubble,
 * and other components can render the customised assistant identity.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable } from 'svelte/store';
import { apiJson } from '$lib/services/api.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentSettings {
	name: string;
	display_name: string;
	avatar_url: string;
	personality: string;
	tone: string;
	greeting: string;
	behavior_rules: string[];
	custom_instructions: string;
	language: string;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

export const AGENT_DEFAULTS: AgentSettings = {
	name: 'Ember',
	display_name: 'Ember',
	avatar_url: '',
	personality: 'warm, professional, knowledgeable',
	tone: 'friendly yet precise',
	greeting: "Hello! I'm {name}, your intelligent assistant.",
	behavior_rules: [],
	custom_instructions: '',
	language: 'en'
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const agentSettings = writable<AgentSettings>({ ...AGENT_DEFAULTS });

/** Whether the initial fetch has completed (success or failure). */
let loaded = false;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Fetch agent settings from the backend. Safe to call from any component;
 * the first successful response is cached and subsequent calls are no-ops
 * unless `force` is true.
 */
export async function loadAgentSettings(force = false): Promise<AgentSettings> {
	if (loaded && !force) {
		let current: AgentSettings = { ...AGENT_DEFAULTS };
		agentSettings.subscribe((v) => (current = v))();
		return current;
	}

	try {
		const data = await apiJson<AgentSettings>('/settings/agent');
		const merged: AgentSettings = { ...AGENT_DEFAULTS, ...data };
		agentSettings.set(merged);
		loaded = true;
		return merged;
	} catch {
		// Use defaults on error (e.g. non-admin user, network issue)
		loaded = true;
		return { ...AGENT_DEFAULTS };
	}
}
