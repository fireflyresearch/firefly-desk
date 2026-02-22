/**
 * User stores for authentication and authorization state.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable, derived } from 'svelte/store';
import { apiJson } from '$lib/services/api.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface User {
	userId: string;
	email: string;
	displayName: string;
	roles: string[];
	permissions: string[];
	pictureUrl?: string;
	department?: string;
	title?: string;
	devMode?: boolean;
}

/** Shape returned by the /api/profile endpoint. */
interface ProfileResponse {
	user_id: string;
	email: string;
	display_name: string;
	roles: string[];
	permissions: string[];
	picture_url?: string | null;
	department?: string | null;
	title?: string | null;
	dev_mode?: boolean;
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export const currentUser = writable<User | null>(null);

/** Whether the current user holds the "admin" role. */
export const isAdmin = derived(currentUser, ($user) =>
	$user !== null && $user.roles.includes('admin')
);

/** Whether there is an authenticated user. */
export const isAuthenticated = derived(currentUser, ($user) => $user !== null);

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

/**
 * Fetch the current user's profile from the backend and populate the
 * {@link currentUser} store.  Safe to call multiple times -- subsequent
 * calls silently succeed even if the fetch fails.
 */
export async function initCurrentUser(): Promise<void> {
	try {
		const profile = await apiJson<ProfileResponse>('/profile');
		currentUser.set({
			userId: profile.user_id,
			email: profile.email,
			displayName: profile.display_name,
			roles: profile.roles ?? [],
			permissions: profile.permissions ?? [],
			pictureUrl: profile.picture_url ?? undefined,
			department: profile.department ?? undefined,
			title: profile.title ?? undefined,
			devMode: profile.dev_mode ?? false
		});
	} catch {
		// If the profile fetch fails (e.g. unauthenticated), leave the
		// store as-is.  Auth guards elsewhere will redirect to login.
	}
}
