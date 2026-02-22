/**
 * SvelteKit ambient type declarations.
 *
 * See https://svelte.dev/docs/kit/types#app.d.ts
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			/** The OIDC access token read from the auth cookie, if present. */
			token: string | null;
			/** Decoded user information from the access token. */
			user: {
				userId: string;
				email: string;
				displayName: string;
				roles: string[];
				permissions: string[];
				pictureUrl?: string;
				department?: string;
				title?: string;
			} | null;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
