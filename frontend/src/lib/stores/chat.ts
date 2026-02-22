/**
 * Chat stores for conversation and message state management.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable } from 'svelte/store';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WidgetDirective {
	widget_id: string;
	type: string;
	props: Record<string, unknown>;
	display: 'inline' | 'panel';
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	widgets: WidgetDirective[];
	timestamp: Date;
	isStreaming?: boolean;
}

export interface Conversation {
	id: string;
	title: string;
	lastMessage: string;
	updatedAt: Date;
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export const conversations = writable<Conversation[]>([]);
export const activeConversationId = writable<string | null>(null);
export const messages = writable<Message[]>([]);
export const isStreaming = writable<boolean>(false);

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

/** Add a complete message to the messages store. */
export function addMessage(message: Message): void {
	messages.update((msgs) => [...msgs, message]);
}

/**
 * Append content to the last assistant message that is currently streaming.
 * If no streaming message exists this is a no-op.
 */
export function updateStreamingMessage(content: string): void {
	messages.update((msgs) => {
		const idx = msgs.findLastIndex((m) => m.role === 'assistant' && m.isStreaming);
		if (idx === -1) return msgs;
		const updated = [...msgs];
		updated[idx] = { ...updated[idx], content: updated[idx].content + content };
		return updated;
	});
}

/**
 * Append a widget directive to the last assistant message that is currently
 * streaming. If no streaming message exists this is a no-op.
 */
export function appendWidget(widget: WidgetDirective): void {
	messages.update((msgs) => {
		const idx = msgs.findLastIndex((m) => m.role === 'assistant' && m.isStreaming);
		if (idx === -1) return msgs;
		const updated = [...msgs];
		updated[idx] = { ...updated[idx], widgets: [...updated[idx].widgets, widget] };
		return updated;
	});
}

/** Mark the currently-streaming assistant message as complete. */
export function finishStreaming(): void {
	messages.update((msgs) =>
		msgs.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m))
	);
	isStreaming.set(false);
}

/** Clear all messages (e.g. when switching conversations). */
export function clearMessages(): void {
	messages.set([]);
}
