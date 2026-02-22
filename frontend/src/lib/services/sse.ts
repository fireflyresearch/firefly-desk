/**
 * Server-Sent Events (SSE) stream parser.
 *
 * Reads a fetch Response body as a stream and parses the SSE wire format
 * (lines prefixed with "event:" and "data:") into structured messages.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SSEMessage {
	event: string;
	data: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

/**
 * Parse an SSE stream from a fetch {@link Response}.
 *
 * @param response   - The fetch response whose body contains the SSE stream.
 * @param onMessage  - Callback invoked for every complete SSE message.
 * @param onError    - Optional callback invoked when a parsing or stream
 *                     error occurs.
 * @param onDone     - Optional callback invoked when the stream ends
 *                     normally.
 */
export async function parseSSEStream(
	response: Response,
	onMessage: (msg: SSEMessage) => void,
	onError?: (error: Error) => void,
	onDone?: () => void
): Promise<void> {
	const body = response.body;
	if (!body) {
		onError?.(new Error('Response body is null'));
		return;
	}

	const reader = body.getReader();
	const decoder = new TextDecoder();

	let buffer = '';
	let currentEvent = '';
	let currentData = '';

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });

			// Process complete lines (SSE lines are terminated by \n).
			const lines = buffer.split('\n');
			// The last element may be an incomplete line -- keep it in the buffer.
			buffer = lines.pop() ?? '';

			for (const line of lines) {
				if (line.startsWith('event:')) {
					currentEvent = line.slice(6).trim();
				} else if (line.startsWith('data:')) {
					currentData += line.slice(5).trim();
				} else if (line === '') {
					// An empty line signals the end of an SSE message.
					if (currentEvent || currentData) {
						try {
							const parsed: Record<string, unknown> = currentData
								? (JSON.parse(currentData) as Record<string, unknown>)
								: {};
							onMessage({ event: currentEvent, data: parsed });
						} catch (err) {
							onError?.(
								new Error(
									`Failed to parse SSE data for event "${currentEvent}": ${String(err)}`
								)
							);
						}
						currentEvent = '';
						currentData = '';
					}
				}
			}
		}

		// Flush any remaining buffered message after the stream ends.
		if (currentEvent || currentData) {
			try {
				const parsed: Record<string, unknown> = currentData
					? (JSON.parse(currentData) as Record<string, unknown>)
					: {};
				onMessage({ event: currentEvent, data: parsed });
			} catch (err) {
				onError?.(
					new Error(
						`Failed to parse final SSE data for event "${currentEvent}": ${String(err)}`
					)
				);
			}
		}
	} catch (err) {
		onError?.(err instanceof Error ? err : new Error(String(err)));
	} finally {
		onDone?.();
	}
}
