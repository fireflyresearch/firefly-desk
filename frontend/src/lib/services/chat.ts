/**
 * Chat service that ties Svelte stores and SSE streaming together.
 *
 * Orchestrates sending a user message to the backend, parsing the SSE
 * response stream, and updating the chat stores in real time.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { get } from 'svelte/store';
import { apiFetch, apiJson } from './api.js';
import { parseSSEStream } from './sse.js';
import type { SSEMessage } from './sse.js';
import type { WidgetDirective, MessageFile, ReasoningStep, TokenUsage } from '../stores/chat.js';
import {
	addMessage,
	updateStreamingMessage,
	replaceStreamingContent,
	upsertWidget,
	appendReasoningStep,
	setReasoningPlan,
	clearReasoningState,
	setUsage,
	finishStreaming,
	isStreaming,
	messages,
	loadConversations
} from '../stores/chat.js';
import { pushPanel } from '../stores/panel.js';
import { startTool, endTool, mergeAgentToolCalls, clearToolState, completedTools } from '../stores/tools.js';

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Options for sending a message with reasoning mode enabled.
 */
export interface SendMessageOptions {
	/** Enable reasoning mode (e.g. ReAct, PlanAndExecute). */
	reasoning?: boolean;
	/** Explicit reasoning pattern name (implies reasoning=true). */
	pattern?: string;
}

/**
 * Send a user message and stream the assistant response.
 *
 * 1. Adds the user message to the messages store.
 * 2. Sets {@link isStreaming} to `true`.
 * 3. Adds an empty, streaming assistant message placeholder.
 * 4. POSTs to the backend SSE endpoint.
 * 5. Parses the SSE stream, updating stores as events arrive.
 * 6. Marks streaming as complete when the stream finishes.
 *
 * @param conversationId - The conversation to send the message to.
 * @param message        - The user's message text.
 * @param fileIds        - Optional file IDs to attach to the message.
 * @param files          - Optional file metadata for display in message bubbles.
 * @param options        - Optional reasoning configuration.
 */
export async function sendMessage(
	conversationId: string,
	message: string,
	fileIds?: string[],
	files?: MessageFile[],
	options?: SendMessageOptions
): Promise<void> {
	const userMessageId = crypto.randomUUID();
	const assistantMessageId = crypto.randomUUID();

	// 1. Add user message (skip internal messages like __setup_init__)
	const isInternalMessage = message.startsWith('__') && message.endsWith('__');
	if (!isInternalMessage) {
		addMessage({
			id: userMessageId,
			role: 'user',
			content: message,
			widgets: [],
			timestamp: new Date(),
			...(fileIds?.length ? { fileIds } : {}),
			...(files?.length ? { files } : {})
		});
	}

	// 2. Set streaming flag
	isStreaming.set(true);

	// 3. Add empty assistant message (streaming placeholder)
	addMessage({
		id: assistantMessageId,
		role: 'assistant',
		content: '',
		widgets: [],
		timestamp: new Date(),
		isStreaming: true
	});

	try {
		// 4. POST to backend (include file_ids and optional reasoning flags)
		const body: Record<string, unknown> = { message, file_ids: fileIds ?? [] };
		if (options?.reasoning) body.reasoning = true;
		if (options?.pattern) body.pattern = options.pattern;

		const response = await apiFetch(
			`/chat/conversations/${encodeURIComponent(conversationId)}/send`,
			{
				method: 'POST',
				body: JSON.stringify(body)
			}
		);

		// 5. Parse SSE stream
		await parseSSEStream(
			response,
			(msg: SSEMessage) => handleSSEEvent(msg),
			(error: Error) => {
				console.error('[ChatService] SSE error:', error);
				finishStreaming();
			},
			() => {
				// onDone callback from stream end -- ensure we clean up
				finishStreaming();
			}
		);

		// 6. Refresh conversation list so new conversations appear in sidebar
		await loadConversations();
	} catch (error) {
		console.error('[ChatService] Failed to send message:', error);
		finishStreaming();
	}
}

/**
 * Submit feedback (thumbs up/down) for an assistant message.
 *
 * @param messageId  - The ID of the message to provide feedback on.
 * @param rating     - Either "up" or "down".
 * @param categories - Optional feedback categories (e.g. "incorrect", "too_verbose").
 * @param comment    - Optional text comment accompanying the feedback.
 */
export async function submitFeedback(
	messageId: string,
	rating: 'up' | 'down',
	categories?: string[],
	comment?: string
): Promise<void> {
	await apiJson('/chat/messages/' + encodeURIComponent(messageId) + '/feedback', {
		method: 'POST',
		body: JSON.stringify({
			rating,
			...(categories?.length ? { categories } : {}),
			...(comment ? { comment } : {})
		})
	});
}

/**
 * Regenerate the last assistant message in a conversation.
 *
 * Finds the last user message in the store and re-sends it, removing the
 * existing assistant response so it can be replaced by a fresh one.
 *
 * @param conversationId - The conversation to regenerate in.
 */
export async function regenerateLastMessage(conversationId: string): Promise<void> {
	const currentMessages = get(messages);

	// Find the last user message to re-send
	const lastUserMessage = [...currentMessages].reverse().find((m) => m.role === 'user');
	if (!lastUserMessage) return;

	// Remove the last assistant message from the store
	messages.update((msgs) => {
		const lastAssistantIdx = msgs.findLastIndex((m) => m.role === 'assistant');
		if (lastAssistantIdx === -1) return msgs;
		return msgs.filter((_, i) => i !== lastAssistantIdx);
	});

	// Re-send the last user message (without re-adding it to the store)
	isStreaming.set(true);

	const assistantMessageId = crypto.randomUUID();
	addMessage({
		id: assistantMessageId,
		role: 'assistant',
		content: '',
		widgets: [],
		timestamp: new Date(),
		isStreaming: true
	});

	try {
		const body: Record<string, unknown> = {
			message: lastUserMessage.content,
			file_ids: lastUserMessage.fileIds ?? []
		};

		const response = await apiFetch(
			`/chat/conversations/${encodeURIComponent(conversationId)}/send`,
			{
				method: 'POST',
				body: JSON.stringify(body)
			}
		);

		await parseSSEStream(
			response,
			(msg: SSEMessage) => handleSSEEvent(msg),
			(error: Error) => {
				console.error('[ChatService] SSE error during regeneration:', error);
				finishStreaming();
			},
			() => {
				finishStreaming();
			}
		);
	} catch (error) {
		console.error('[ChatService] Failed to regenerate message:', error);
		finishStreaming();
	}
}

// ---------------------------------------------------------------------------
// Internal SSE event handler
// ---------------------------------------------------------------------------

function handleSSEEvent(msg: SSEMessage): void {
	switch (msg.event) {
		case 'token': {
			const content = msg.data.content ?? msg.data.token;
			if (typeof content === 'string') {
				updateStreamingMessage(content);
			}
			break;
		}

		case 'content_replace': {
			const content = msg.data.content as string;
			if (typeof content === 'string') {
				replaceStreamingContent(content);
			}
			break;
		}

		case 'widget': {
			const widget: WidgetDirective = {
				widget_id: msg.data.widget_id as string,
				type: msg.data.type as string,
				props: (msg.data.props as Record<string, unknown>) ?? {},
				display: (msg.data.display as 'inline' | 'panel') ?? 'inline'
			};
			upsertWidget(widget);

			if (widget.display === 'panel') {
				pushPanel({
					id: widget.widget_id,
					widgetType: widget.type,
					props: widget.props,
					title: widget.type
				});
			}
			break;
		}

		case 'tool_start': {
			const toolId = (msg.data.tool_call_id as string) ?? crypto.randomUUID();
			const toolName = (msg.data.tool_name as string) ?? 'Unknown tool';
			startTool(toolId, toolName);
			break;
		}

		case 'tool_end': {
			const toolId = msg.data.tool_call_id as string;
			const result = msg.data.result as Record<string, unknown> | undefined;
			if (toolId) endTool(toolId, result);
			break;
		}

		case 'tool_summary': {
			const toolCalls = msg.data.tool_calls as
				| Array<{ tool_name: string; tool_call_id?: string; success?: boolean }>
				| undefined;
			if (toolCalls) mergeAgentToolCalls(toolCalls);
			break;
		}

		case 'confirmation': {
			const widget: WidgetDirective = {
				widget_id: (msg.data.confirmation_id as string) ?? crypto.randomUUID(),
				type: 'confirmation',
				props: {
					confirmation_id: msg.data.confirmation_id as string,
					tool_name: msg.data.tool_name as string,
					tool_call_id: msg.data.tool_call_id as string | undefined,
					risk_level: msg.data.risk_level as string,
					message: msg.data.message as string | undefined,
					parameters: msg.data.parameters as Record<string, unknown> | undefined,
					description: msg.data.description as string | undefined,
					expires_at: msg.data.expires_at as number | undefined
				},
				display: 'inline'
			};
			upsertWidget(widget);
			break;
		}

		case 'reasoning_step': {
			const step: ReasoningStep = {
				step_number: msg.data.step_number as number,
				step_type: msg.data.step_type as string,
				description: msg.data.description as string,
				status: msg.data.status as string
			};
			appendReasoningStep(step);
			break;
		}

		case 'plan': {
			const steps =
				(msg.data.steps as Array<{ description: string; status: string }>) ?? [];
			setReasoningPlan(steps);
			break;
		}

		case 'usage': {
			const usage: TokenUsage = {
				input_tokens: (msg.data.input_tokens as number) ?? 0,
				output_tokens: (msg.data.output_tokens as number) ?? 0,
				total_tokens: (msg.data.total_tokens as number) ?? 0,
				cost_usd: (msg.data.cost_usd as number) ?? 0,
				model: (msg.data.model as string) ?? ''
			};
			setUsage(usage);
			break;
		}

		case 'error': {
			const errorMsg = msg.data.message;
			if (typeof errorMsg === 'string') {
				console.error('[ChatService] Server error:', errorMsg);
			}
			finishStreaming();
			break;
		}

		case 'done': {
			const tools = get(completedTools);
			const toolCount = typeof msg.data.tool_count === 'number' ? msg.data.tool_count : undefined;
			finishStreaming(tools.length > 0 ? tools : undefined, toolCount);
			clearToolState();
			clearReasoningState();
			break;
		}

		default: {
			// Unknown event type -- ignore gracefully
			break;
		}
	}
}
