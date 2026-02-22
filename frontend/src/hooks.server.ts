/**
 * SvelteKit server hooks -- authentication guard.
 *
 * On every request the hook reads the auth cookie, decodes the JWT
 * payload to populate `event.locals`, and redirects unauthenticated
 * users away from protected routes.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { redirect, type Handle } from '@sveltejs/kit';

/** Name of the cookie that carries the access token. */
const AUTH_COOKIE = 'flydek_token';

/** Route prefixes that do not require authentication. */
const PUBLIC_PREFIXES = ['/auth'];

// ---------------------------------------------------------------------------
// JWT decode (server-side, no verification -- token came from our own
// callback handler which received it directly from the OIDC provider).
// ---------------------------------------------------------------------------

function decodeJwtPayload(token: string): Record<string, unknown> | null {
	try {
		const parts = token.split('.');
		if (parts.length !== 3) return null;
		const json = Buffer.from(parts[1], 'base64url').toString('utf-8');
		return JSON.parse(json) as Record<string, unknown>;
	} catch {
		return null;
	}
}

// ---------------------------------------------------------------------------
// Handle hook
// ---------------------------------------------------------------------------

export const handle: Handle = async ({ event, resolve }) => {
	// 1. Read the auth cookie
	const token = event.cookies.get(AUTH_COOKIE) ?? null;

	// 2. Populate locals with token and decoded user info
	event.locals.token = token;
	event.locals.user = null;

	if (token) {
		const claims = decodeJwtPayload(token);
		if (claims) {
			const realmAccess = claims['realm_access'] as { roles?: string[] } | undefined;
			event.locals.user = {
				userId: (claims['sub'] as string) ?? '',
				email: (claims['email'] as string) ?? '',
				displayName:
					(claims['name'] as string) ??
					(claims['preferred_username'] as string) ??
					(claims['email'] as string) ??
					'',
				roles: Array.isArray(realmAccess?.roles) ? realmAccess.roles : []
			};
		}
	}

	// 3. Route protection -- redirect to login if not authenticated
	const { pathname } = event.url;
	const isPublic = PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));

	if (!isPublic && !token) {
		throw redirect(302, '/auth/login');
	}

	return resolve(event);
};
