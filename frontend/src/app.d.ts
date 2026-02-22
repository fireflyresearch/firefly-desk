// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
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
			} | null;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
