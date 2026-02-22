/**
 * Server-side load for the login page.
 *
 * The login page fetches OIDC providers from the backend API at
 * runtime, so there is no server data to pass.  This file exists
 * to ensure the page is rendered server-side and that the dev-mode
 * redirect can be applied here if needed in the future.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	return {};
};
