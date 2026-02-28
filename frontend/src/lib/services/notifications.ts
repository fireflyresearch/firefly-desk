/**
 * Notification service for fetching and dismissing notifications.
 *
 * Notifications are a unified view of recent jobs and workflows surfaced
 * to the user as lightweight status items.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { apiFetch, apiJson } from './api.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AppNotification {
	id: string;
	type: 'job' | 'workflow' | 'email';
	title: string;
	status: 'pending' | 'running' | 'completed' | 'failed';
	progress?: number | null;
	created_at: string | null;
	updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Fetch recent notifications (jobs + workflows) for the current user.
 */
export async function fetchNotifications(): Promise<AppNotification[]> {
	const data = await apiJson<{ notifications: AppNotification[] }>('/notifications');
	return data.notifications;
}

/**
 * Dismiss a single notification so it no longer appears in the list.
 */
export async function dismissNotification(id: string): Promise<void> {
	await apiFetch(`/notifications/${encodeURIComponent(id)}/dismiss`, { method: 'PATCH' });
}
