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
import type { WidgetDirective } from '../stores/chat.js';
import {
	addMessage,
	updateStreamingMessage,
	appendWidget,
	finishStreaming,
	isStreaming,
	messages
} from '../stores/chat.js';
import { pushPanel } from '../stores/panel.js';
import { startTool, endTool, clearToolState, completedTools } from '../stores/tools.js';

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

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
 */
export async function sendMessage(conversationId: string, message: string): Promise<void> {
	const userMessageId = crypto.randomUUID();
	const assistantMessageId = crypto.randomUUID();

	// 1. Add user message
	addMessage({
		id: userMessageId,
		role: 'user',
		content: message,
		widgets: [],
		timestamp: new Date()
	});

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
		// 4. POST to backend
		const response = await apiFetch(
			`/chat/conversations/${encodeURIComponent(conversationId)}/send`,
			{
				method: 'POST',
				body: JSON.stringify({ message })
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
	} catch (error) {
		console.error('[ChatService] Failed to send message:', error);
		finishStreaming();
	}
}

/**
 * Check whether this is a first-run instance (no seed data loaded).
 */
export async function checkFirstRun(): Promise<boolean> {
	try {
		const data = await apiJson<{ is_first_run: boolean }>('/setup/first-run');
		return data.is_first_run;
	} catch {
		return false;
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

		case 'widget': {
			const widget: WidgetDirective = {
				widget_id: msg.data.widget_id as string,
				type: msg.data.type as string,
				props: (msg.data.props as Record<string, unknown>) ?? {},
				display: (msg.data.display as 'inline' | 'panel') ?? 'inline'
			};
			appendWidget(widget);

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
			finishStreaming(tools.length > 0 ? tools : undefined);
			clearToolState();
			break;
		}

		default: {
			// Unknown event type -- ignore gracefully
			break;
		}
	}
}
