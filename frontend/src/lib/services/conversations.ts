/**
 * Conversation service for managing conversation CRUD operations.
 *
 * Provides functions to list, create, rename, delete conversations
 * and fetch messages for a given conversation.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { apiFetch, apiJson } from './api.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ApiConversation {
	id: string;
	title: string | null;
	user_id: string;
	model_id: string | null;
	metadata: Record<string, unknown>;
	status: string;
	message_count: number;
	created_at: string | null;
	updated_at: string | null;
}

export interface ApiMessage {
	id: string;
	conversation_id: string;
	role: 'user' | 'assistant';
	content: string;
	metadata: Record<string, unknown>;
	created_at: string | null;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Fetch all conversations for the current user.
 */
export async function fetchConversations(): Promise<ApiConversation[]> {
	return apiJson<ApiConversation[]>('/conversations');
}

/**
 * Create a new conversation on the backend.
 */
export async function createConversation(
	title?: string
): Promise<ApiConversation> {
	return apiJson<ApiConversation>('/conversations', {
		method: 'POST',
		body: JSON.stringify({ title: title ?? null })
	});
}

/**
 * Rename an existing conversation.
 */
export async function renameConversation(
	id: string,
	title: string
): Promise<void> {
	await apiFetch(`/conversations/${encodeURIComponent(id)}`, {
		method: 'PATCH',
		body: JSON.stringify({ title })
	});
}

/**
 * Delete (soft-delete) a conversation.
 */
export async function deleteConversation(id: string): Promise<void> {
	await apiFetch(`/conversations/${encodeURIComponent(id)}`, {
		method: 'DELETE'
	});
}

/**
 * Fetch messages for a conversation.
 */
export async function fetchMessages(
	conversationId: string
): Promise<ApiMessage[]> {
	return apiJson<ApiMessage[]>(
		`/conversations/${encodeURIComponent(conversationId)}/messages`
	);
}
