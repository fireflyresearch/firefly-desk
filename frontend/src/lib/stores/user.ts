/**
 * User stores for authentication and authorization state.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable, derived } from 'svelte/store';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface User {
	userId: string;
	email: string;
	displayName: string;
	roles: string[];
	permissions: string[];
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
