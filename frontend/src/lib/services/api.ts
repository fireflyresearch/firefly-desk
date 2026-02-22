/**
 * Base API client with auth token injection.
 *
 * All paths are relative to API_BASE which is reverse-proxied by the
 * SvelteKit dev server (or production server) to the FastAPI backend.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

const API_BASE = '/api';

/** Key used for persisting the auth token in session storage. */
const TOKEN_KEY = 'firefly_auth_token';

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

export function getToken(): string | null {
	if (typeof sessionStorage === 'undefined') return null;
	return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
	sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
	sessionStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// API fetch wrappers
// ---------------------------------------------------------------------------

/**
 * Low-level fetch wrapper that prepends {@link API_BASE} and injects the
 * stored auth token as a Bearer header when available.
 *
 * @throws {Error} On non-2xx responses with the status text and body.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
	const url = `${API_BASE}${path}`;

	const headers = new Headers(options.headers);
	const token = getToken();
	if (token) {
		headers.set('Authorization', `Bearer ${token}`);
	}
	if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
		headers.set('Content-Type', 'application/json');
	}

	const response = await fetch(url, { ...options, headers });

	if (!response.ok) {
		const body = await response.text().catch(() => '');
		throw new Error(`API ${response.status} ${response.statusText}: ${body}`);
	}

	return response;
}

/**
 * Convenience wrapper that calls {@link apiFetch} and parses the response as
 * JSON, returning the typed result.
 */
export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
	const response = await apiFetch(path, options);
	return (await response.json()) as T;
}
