/**
 * SvelteKit server hooks -- authentication guard.
 *
 * In dev mode (FLYDESK_DEV_MODE=true), authentication is bypassed
 * and a synthetic admin user is injected into locals.
 *
 * In production, the hook reads the auth cookie, decodes the JWT
 * payload to populate `event.locals`, and redirects unauthenticated
 * users away from protected routes.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { redirect, type Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

/** Name of the cookie that carries the access token. */
const AUTH_COOKIE = 'flydesk_token';

/** Route prefixes that do not require authentication. */
const PUBLIC_PREFIXES = ['/auth', '/setup'];

function isDevMode(): boolean {
	return (env.FLYDESK_DEV_MODE ?? 'true').toLowerCase() === 'true';
}

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
	const devMode = isDevMode();

	// Dev mode: inject a synthetic admin user, skip all auth checks
	if (devMode) {
		event.locals.token = 'dev-token';
		event.locals.user = {
			userId: 'dev-user-001',
			email: 'admin@localhost',
			displayName: 'Dev Admin',
			roles: ['admin', 'operator'],
			permissions: [],
			pictureUrl: undefined,
			department: undefined,
			title: undefined
		};
		return resolve(event);
	}

	// Production mode: read cookie and decode JWT
	const token = event.cookies.get(AUTH_COOKIE) ?? null;

	event.locals.token = token;
	event.locals.user = null;

	if (token) {
		const claims = decodeJwtPayload(token);
		if (claims) {
			// NOTE: The claim paths below (realm_access, resource_access) are
			// intentionally Keycloak-specific.  This lightweight extraction is
			// only used for the SvelteKit route guard and initial page render.
			// The canonical, provider-agnostic user profile is loaded via
			// `initCurrentUser()` which calls `/api/profile` and lets the
			// backend resolve claims for any configured OIDC provider.
			const realmAccess = claims['realm_access'] as { roles?: string[] } | undefined;
			const flatRoles = claims['roles'] as string[] | undefined;
			const resourceAccess = claims['resource_access'] as
				| Record<string, { roles?: string[] }>
				| undefined;

			// Merge permissions from resource_access claims
			const permissions: string[] = [];
			if (resourceAccess) {
				for (const [, resource] of Object.entries(resourceAccess)) {
					if (Array.isArray(resource?.roles)) {
						permissions.push(...resource.roles);
					}
				}
			}

			event.locals.user = {
				userId: (claims['sub'] as string) ?? '',
				email: (claims['email'] as string) ?? '',
				displayName:
					(claims['name'] as string) ??
					(claims['preferred_username'] as string) ??
					(claims['email'] as string) ??
					'',
				roles: Array.isArray(realmAccess?.roles)
					? realmAccess.roles
					: Array.isArray(flatRoles)
						? flatRoles
						: [],
				permissions,
				pictureUrl: (claims['picture'] as string) ?? undefined,
				department: (claims['department'] as string) ?? undefined,
				title: (claims['title'] as string) ?? undefined
			};
		}
	}

	// Route protection -- redirect to login if not authenticated
	const { pathname } = event.url;
	const isPublic = PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));

	if (!isPublic && !token) {
		throw redirect(302, '/auth/login');
	}

	return resolve(event);
};
