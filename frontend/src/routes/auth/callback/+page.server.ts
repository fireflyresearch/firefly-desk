/**
 * Server-side load for the OIDC callback page.
 *
 * The callback page handles the OAuth code exchange client-side by
 * posting to the backend /api/auth/callback endpoint.  This server
 * load exists to ensure the page is rendered and can receive the
 * authorization code and state from the IdP redirect.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	return {};
};
