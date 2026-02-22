/**
 * Server-side load for the login page.
 *
 * Exposes the public OIDC configuration (issuer URL, client ID, and
 * redirect URI) so the client can build the authorization redirect.
 * The client secret is intentionally excluded -- it is only used
 * server-side during the token exchange in the callback handler.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	return {
		issuerUrl: env.FLYDEK_OIDC_ISSUER_URL ?? '',
		clientId: env.FLYDEK_OIDC_CLIENT_ID ?? '',
		redirectUri: env.FLYDEK_OIDC_REDIRECT_URI ?? 'http://localhost:3000/auth/callback'
	};
};
