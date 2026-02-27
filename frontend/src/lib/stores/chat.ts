/**
 * Chat stores for conversation and message state management.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable } from 'svelte/store';
import {
	fetchConversations as apiFetchConversations,
	fetchMessages as apiFetchMessages,
	createConversation as apiCreateConversation,
	fetchFolders as apiFetchFolders
} from '$lib/services/conversations.js';
import type { ApiFolder } from '$lib/services/conversations.js';
import type { ToolExecution } from './tools.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WidgetDirective {
	widget_id: string;
	type: string;
	props: Record<string, unknown>;
	display: 'inline' | 'panel';
}

export interface MessageFile {
	id: string;
	filename: string;
	content_type: string;
	file_size: number;
}

export interface TokenUsage {
	input_tokens: number;
	output_tokens: number;
	total_tokens: number;
	cost_usd: number;
	model: string;
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	widgets: WidgetDirective[];
	timestamp: Date;
	isStreaming?: boolean;
	toolExecutions?: ToolExecution[];
	fileIds?: string[];
	files?: MessageFile[];
	usage?: TokenUsage;
	/** Number of tools available to the agent for this turn (diagnostic). */
	toolCount?: number;
}

export interface ReasoningStep {
	step_number: number;
	step_type: string;
	description: string;
	status: string;
}

export interface ReasoningPlanStep {
	description: string;
	status: string;
}

export interface ConversationMetadata {
	pinned?: boolean;
	archived?: boolean;
	folder_id?: string;
	[key: string]: unknown;
}

export interface Conversation {
	id: string;
	title: string;
	lastMessage: string;
	updatedAt: Date;
	metadata: ConversationMetadata;
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export const conversations = writable<Conversation[]>([]);
export const activeConversationId = writable<string | null>(null);
export const messages = writable<Message[]>([]);
export const isStreaming = writable<boolean>(false);
export const reasoningSteps = writable<ReasoningStep[]>([]);
export const reasoningPlan = writable<ReasoningPlanStep[]>([]);
export const folders = writable<ApiFolder[]>([]);

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
 * Replace the entire content of the last streaming assistant message.
 * Used after widget parsing to strip raw widget directives from the content.
 * If no streaming message exists this is a no-op.
 */
export function replaceStreamingContent(content: string): void {
	messages.update((msgs) => {
		const idx = msgs.findLastIndex((m) => m.role === 'assistant' && m.isStreaming);
		if (idx === -1) return msgs;
		const updated = [...msgs];
		updated[idx] = { ...updated[idx], content };
		return updated;
	});
}

/**
 * Upsert a widget directive into the last streaming assistant message.
 * If a widget with the same `widget_id` already exists, its props are merged.
 * Also deduplicates by type + title to prevent the same widget appearing twice
 * when the LLM outputs duplicate directives with different auto-generated IDs.
 */
export function upsertWidget(widget: WidgetDirective): void {
	messages.update((msgs) => {
		const idx = msgs.findLastIndex((m) => m.role === 'assistant' && m.isStreaming);
		if (idx === -1) return msgs;
		const updated = [...msgs];
		const existingWidgets = [...updated[idx].widgets];

		// Match by widget_id first
		const widgetIdx = existingWidgets.findIndex((w) => w.widget_id === widget.widget_id);
		if (widgetIdx >= 0) {
			existingWidgets[widgetIdx] = {
				...existingWidgets[widgetIdx],
				props: { ...existingWidgets[widgetIdx].props, ...widget.props }
			};
		} else {
			// Content-based dedup: skip if same type + same title already exists
			const title = (widget.props as Record<string, unknown>).title;
			const duplicate =
				title &&
				existingWidgets.some(
					(w) => w.type === widget.type && (w.props as Record<string, unknown>).title === title
				);
			if (!duplicate) {
				existingWidgets.push(widget);
			}
		}
		updated[idx] = { ...updated[idx], widgets: existingWidgets };
		return updated;
	});
}

/** Append a reasoning step to the current reasoning steps store. */
export function appendReasoningStep(step: ReasoningStep): void {
	reasoningSteps.update((steps) => [...steps, step]);
}

/** Set the reasoning plan steps. */
export function setReasoningPlan(steps: ReasoningPlanStep[]): void {
	reasoningPlan.set(steps);
}

/** Clear reasoning state (call when streaming finishes). */
export function clearReasoningState(): void {
	reasoningSteps.set([]);
	reasoningPlan.set([]);
}

/**
 * Set token usage on the last assistant message that is currently streaming.
 * If no streaming message exists this is a no-op.
 */
export function setUsage(usage: TokenUsage): void {
	messages.update((msgs) => {
		const idx = msgs.findLastIndex((m) => m.role === 'assistant' && m.isStreaming);
		if (idx === -1) return msgs;
		const updated = [...msgs];
		updated[idx] = { ...updated[idx], usage };
		return updated;
	});
}

/** Mark the currently-streaming assistant message as complete. */
export function finishStreaming(toolExecutions?: ToolExecution[], toolCount?: number): void {
	messages.update((msgs) =>
		msgs.map((m) =>
			m.isStreaming
				? {
						...m,
						isStreaming: false,
						...(toolExecutions?.length ? { toolExecutions } : {}),
						...(toolCount !== undefined ? { toolCount } : {})
					}
				: m
		)
	);
	isStreaming.set(false);
}

/** Clear all messages (e.g. when switching conversations). */
export function clearMessages(): void {
	messages.set([]);
}

// ---------------------------------------------------------------------------
// Conversation management
// ---------------------------------------------------------------------------

/**
 * Load conversations from the backend and populate the conversations store.
 */
export async function loadConversations(): Promise<void> {
	try {
		const apiConversations = await apiFetchConversations();
		conversations.set(
			apiConversations.map((c) => ({
				id: c.id,
				title: c.title ?? 'Untitled',
				lastMessage: '',
				updatedAt: new Date(c.updated_at ?? c.created_at ?? new Date().toISOString()),
				metadata: (c.metadata ?? {}) as ConversationMetadata
			}))
		);
	} catch (error) {
		console.error('[ChatStore] Failed to load conversations:', error);
	}
}

/**
 * Load folders from the backend and populate the folders store.
 */
export async function loadFolders(): Promise<void> {
	try {
		const apiFolders = await apiFetchFolders();
		folders.set(apiFolders);
	} catch (error) {
		console.error('[ChatStore] Failed to load folders:', error);
	}
}

/**
 * Select a conversation and load its messages from the backend.
 */
export async function selectConversation(id: string): Promise<void> {
	activeConversationId.set(id);
	clearMessages();

	try {
		const apiMessages = await apiFetchMessages(id);
		messages.set(
			apiMessages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				widgets: (m.metadata?.widgets as WidgetDirective[]) ?? [],
				timestamp: new Date(m.created_at ?? new Date().toISOString()),
				...(m.metadata?.usage ? { usage: m.metadata.usage as TokenUsage } : {})
			}))
		);
	} catch (error) {
		console.error('[ChatStore] Failed to load messages:', error);
	}
}

/**
 * Create a new conversation on the backend and set it as active.
 */
export async function createNewConversation(): Promise<string> {
	try {
		const apiConv = await apiCreateConversation();
		const conv: Conversation = {
			id: apiConv.id,
			title: apiConv.title ?? 'New Conversation',
			lastMessage: '',
			updatedAt: new Date(apiConv.updated_at ?? apiConv.created_at ?? new Date().toISOString()),
			metadata: (apiConv.metadata ?? {}) as ConversationMetadata
		};
		conversations.update((convs) => [conv, ...convs]);
		activeConversationId.set(conv.id);
		clearMessages();
		return conv.id;
	} catch (error) {
		console.error('[ChatStore] Failed to create conversation:', error);
		// Fallback: generate a local ID so the UI can still function
		const fallbackId = crypto.randomUUID();
		activeConversationId.set(fallbackId);
		clearMessages();
		return fallbackId;
	}
}
