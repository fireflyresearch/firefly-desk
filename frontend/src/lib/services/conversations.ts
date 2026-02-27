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

export interface ApiFolder {
	id: string;
	name: string;
	icon: string;
	sort_order: number;
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

/**
 * Update a conversation's metadata (used for pin, archive, move to folder).
 */
export async function updateConversationMetadata(
	id: string,
	metadata: Record<string, unknown>
): Promise<void> {
	await apiFetch(`/conversations/${encodeURIComponent(id)}`, {
		method: 'PATCH',
		body: JSON.stringify({ metadata })
	});
}

/**
 * Pin or unpin a conversation.
 */
export async function pinConversation(
	id: string,
	pinned: boolean
): Promise<void> {
	// We need to fetch current metadata first to merge
	const conv = await apiJson<ApiConversation>(
		`/conversations/${encodeURIComponent(id)}`
	);
	const metadata = { ...conv.metadata, pinned };
	await updateConversationMetadata(id, metadata);
}

/**
 * Archive a conversation.
 */
export async function archiveConversation(
	id: string,
	archived: boolean
): Promise<void> {
	const conv = await apiJson<ApiConversation>(
		`/conversations/${encodeURIComponent(id)}`
	);
	const metadata = { ...conv.metadata, archived };
	await updateConversationMetadata(id, metadata);
}

/**
 * Move a conversation into a folder (or remove from folder with null).
 */
export async function moveToFolder(
	id: string,
	folderId: string | null
): Promise<void> {
	const conv = await apiJson<ApiConversation>(
		`/conversations/${encodeURIComponent(id)}`
	);
	const { folder_id: _, ...rest } = conv.metadata;
	const metadata = folderId ? { ...rest, folder_id: folderId } : rest;
	await updateConversationMetadata(id, metadata);
}

// ---------------------------------------------------------------------------
// Folder API
// ---------------------------------------------------------------------------

export async function fetchFolders(): Promise<ApiFolder[]> {
	return apiJson<ApiFolder[]>('/conversations/folders');
}

export async function createFolder(name: string, icon: string = 'folder'): Promise<ApiFolder> {
	return apiJson<ApiFolder>('/conversations/folders', {
		method: 'POST',
		body: JSON.stringify({ name, icon })
	});
}

export async function renameFolder(
	id: string,
	name: string,
	icon?: string
): Promise<void> {
	await apiFetch(`/conversations/folders/${encodeURIComponent(id)}`, {
		method: 'PATCH',
		body: JSON.stringify({ name, ...(icon !== undefined && { icon }) })
	});
}

export async function deleteFolder(id: string): Promise<void> {
	await apiFetch(`/conversations/folders/${encodeURIComponent(id)}`, {
		method: 'DELETE'
	});
}

export async function reorderFolders(folderIds: string[]): Promise<void> {
	await apiFetch('/conversations/folders/reorder', {
		method: 'PUT',
		body: JSON.stringify({ folder_ids: folderIds })
	});
}
