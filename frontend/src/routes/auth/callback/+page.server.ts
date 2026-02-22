/**
 * OIDC callback handler.
 *
 * Exchanges the authorization code for tokens, stores the access
 * token in a secure httpOnly cookie, and redirects to the app root.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { env } from '$env/dynamic/private';
import { redirect, error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

/** Name of the cookie that carries the access token. */
const AUTH_COOKIE = 'flydek_token';

export const load: PageServerLoad = async ({ url, cookies }) => {
	const code = url.searchParams.get('code');
	const state = url.searchParams.get('state');

	if (!code) {
		const errorDescription = url.searchParams.get('error_description') ?? 'Missing authorization code';
		throw error(400, errorDescription);
	}

	// -----------------------------------------------------------------------
	// Exchange the authorization code for tokens
	// -----------------------------------------------------------------------

	const issuerUrl = (env.FLYDEK_OIDC_ISSUER_URL ?? '').replace(/\/+$/, '');
	const clientId = env.FLYDEK_OIDC_CLIENT_ID ?? '';
	const clientSecret = env.FLYDEK_OIDC_CLIENT_SECRET ?? '';
	const redirectUri = env.FLYDEK_OIDC_REDIRECT_URI ?? 'http://localhost:3000/auth/callback';

	const tokenUrl = `${issuerUrl}/protocol/openid-connect/token`;

	const body = new URLSearchParams({
		grant_type: 'authorization_code',
		code,
		redirect_uri: redirectUri,
		client_id: clientId,
		client_secret: clientSecret
	});

	const tokenResponse = await fetch(tokenUrl, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: body.toString()
	});

	if (!tokenResponse.ok) {
		const detail = await tokenResponse.text().catch(() => '');
		console.error('OIDC token exchange failed:', tokenResponse.status, detail);
		throw error(502, 'Authentication failed: could not exchange authorization code');
	}

	const tokens = (await tokenResponse.json()) as {
		access_token: string;
		id_token?: string;
		refresh_token?: string;
		expires_in?: number;
		token_type?: string;
	};

	// -----------------------------------------------------------------------
	// Store the access token in a secure cookie
	// -----------------------------------------------------------------------

	const maxAge = tokens.expires_in ?? 3600;

	cookies.set(AUTH_COOKIE, tokens.access_token, {
		path: '/',
		httpOnly: true,
		secure: true,
		sameSite: 'lax',
		maxAge
	});

	// Also store the ID token if present (used for user claims on the client).
	if (tokens.id_token) {
		cookies.set('flydek_id_token', tokens.id_token, {
			path: '/',
			httpOnly: false, // readable by client JS for claim extraction
			secure: true,
			sameSite: 'lax',
			maxAge
		});
	}

	// -----------------------------------------------------------------------
	// Redirect to the application root
	// -----------------------------------------------------------------------

	throw redirect(302, '/');
};
