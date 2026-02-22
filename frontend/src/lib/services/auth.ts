/**
 * Client-side OIDC authentication utilities.
 *
 * These helpers build authorization URLs, decode ID tokens, and map
 * token claims to the application's User type.  JWT signature
 * verification is intentionally skipped on the client -- the server
 * callback handler trusts the token received directly from the OIDC
 * provider over a back-channel request.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { User } from '$lib/stores/user';

// ---------------------------------------------------------------------------
// Authorization URL
// ---------------------------------------------------------------------------

/**
 * Build the OIDC authorization redirect URL.
 *
 * Uses the Keycloak-convention token endpoint path
 * (`/protocol/openid-connect/auth`).  For a fully generic OIDC
 * implementation the endpoint would be discovered from
 * `.well-known/openid-configuration`; this is acceptable for the MVP.
 */
export function buildAuthUrl(
	issuerUrl: string,
	clientId: string,
	redirectUri: string,
	state: string
): string {
	const base = issuerUrl.replace(/\/+$/, '');
	const params = new URLSearchParams({
		response_type: 'code',
		client_id: clientId,
		redirect_uri: redirectUri,
		scope: 'openid profile email roles',
		state
	});
	return `${base}/protocol/openid-connect/auth?${params.toString()}`;
}

// ---------------------------------------------------------------------------
// JWT helpers (decode only -- no verification)
// ---------------------------------------------------------------------------

/**
 * Decode a Base64url-encoded string to a UTF-8 string.
 */
function base64UrlDecode(input: string): string {
	// Replace URL-safe characters and pad to a multiple of 4.
	const base64 = input.replace(/-/g, '+').replace(/_/g, '/');
	const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
	return atob(padded);
}

/**
 * Parse the payload of a JWT without verifying the signature.
 *
 * This is suitable for extracting user claims on the client side when
 * the token has already been validated server-side.
 */
export function parseIdToken(idToken: string): Record<string, unknown> {
	const parts = idToken.split('.');
	if (parts.length !== 3) {
		throw new Error('Invalid JWT: expected three dot-separated segments');
	}
	const payload = parts[1];
	try {
		return JSON.parse(base64UrlDecode(payload)) as Record<string, unknown>;
	} catch {
		throw new Error('Invalid JWT: could not decode payload');
	}
}

// ---------------------------------------------------------------------------
// Claims -> User mapping
// ---------------------------------------------------------------------------

/**
 * Map OIDC / Keycloak token claims to the application {@link User} type.
 *
 * Keycloak typically places realm roles under
 * `realm_access.roles` and resource roles under
 * `resource_access.<client>.roles`.  We merge realm roles into the
 * top-level `roles` array and leave permissions empty for now (they
 * can be populated from a resource-access claim or a separate
 * endpoint later).
 */
export function claimsToUser(claims: Record<string, unknown>): User {
	const realmAccess = claims['realm_access'] as { roles?: string[] } | undefined;
	const roles: string[] = Array.isArray(realmAccess?.roles) ? realmAccess.roles : [];

	return {
		userId: (claims['sub'] as string) ?? '',
		email: (claims['email'] as string) ?? '',
		displayName:
			(claims['name'] as string) ??
			(claims['preferred_username'] as string) ??
			(claims['email'] as string) ??
			'',
		roles,
		permissions: []
	};
}
