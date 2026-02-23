/**
 * Setup page server load -- redirects to "/" when setup is already complete,
 * otherwise passes the current setup status to the client.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const res = await fetch('/api/setup/status');
		if (res.ok) {
			const status = await res.json();
			if (status.setup_completed) {
				throw redirect(303, '/');
			}
			return { status };
		}
	} catch (e: unknown) {
		// redirect() throws a special object -- let it propagate
		if (e && typeof e === 'object' && 'status' in e) throw e;
	}
	return { status: null };
};
