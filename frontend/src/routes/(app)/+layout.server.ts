/**
 * Server-side layout data for the authenticated app group.
 *
 * Passes the decoded user information from hooks to all child pages
 * so it is available in `$page.data.user`.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	return {
		user: locals.user,
		token: locals.token
	};
};
