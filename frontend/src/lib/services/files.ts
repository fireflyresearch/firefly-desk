/**
 * File upload service for chat attachments.
 *
 * Provides functions to upload, retrieve, and delete files
 * associated with chat conversations.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { getToken } from './api.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UploadedFile {
	id: string;
	filename: string;
	content_type: string;
	file_size: number;
	conversation_id: string | null;
	extracted_text: string | null;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Upload a file to the backend.
 *
 * Uses raw fetch instead of apiFetch to avoid setting a JSON Content-Type
 * header, allowing the browser to set the multipart boundary automatically.
 */
export async function uploadFile(
	file: File,
	conversationId: string
): Promise<UploadedFile> {
	const formData = new FormData();
	formData.append('file', file);
	formData.append('conversation_id', conversationId);

	const headers: Record<string, string> = {};
	const token = getToken();
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}

	const response = await fetch('/api/chat/upload', {
		method: 'POST',
		body: formData,
		headers
	});

	if (!response.ok) {
		const body = await response.text().catch(() => '');
		throw new Error(`Upload failed: ${response.status} ${response.statusText}: ${body}`);
	}

	return response.json();
}
