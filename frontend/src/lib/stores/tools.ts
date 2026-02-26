/**
 * Tool execution tracking stores.
 *
 * Tracks the lifecycle of tool calls during an agent turn so the UI can
 * show contextual thinking animations and post-turn summaries.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable } from 'svelte/store';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ToolExecution {
	id: string;
	toolName: string;
	status: 'running' | 'completed' | 'error';
	startedAt: Date;
	completedAt?: Date;
	result?: Record<string, unknown>;
	duration?: number;
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export const activeTools = writable<ToolExecution[]>([]);
export const completedTools = writable<ToolExecution[]>([]);

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

/** Record the start of a tool execution. */
export function startTool(id: string, toolName: string): void {
	const execution: ToolExecution = {
		id,
		toolName,
		status: 'running',
		startedAt: new Date()
	};
	activeTools.update((tools) => [...tools, execution]);
}

/** Record the completion of a tool execution. */
export function endTool(id: string, result?: Record<string, unknown>): void {
	activeTools.update((tools) => {
		const idx = tools.findIndex((t) => t.id === id);
		if (idx === -1) return tools;

		const tool = tools[idx];
		const completedTool: ToolExecution = {
			...tool,
			status: 'completed',
			completedAt: new Date(),
			result,
			duration: new Date().getTime() - tool.startedAt.getTime()
		};

		// Move from active to completed
		completedTools.update((completed) => [...completed, completedTool]);

		const updated = [...tools];
		updated.splice(idx, 1);
		return updated;
	});
}

/** Merge agent tool calls from a TOOL_SUMMARY event into completedTools. */
export function mergeAgentToolCalls(
	toolCalls: Array<{ tool_name: string; tool_call_id?: string; success?: boolean }>
): void {
	if (!toolCalls || toolCalls.length === 0) return;

	const now = new Date();
	const entries: ToolExecution[] = toolCalls.map((tc) => ({
		id: tc.tool_call_id || crypto.randomUUID(),
		toolName: tc.tool_name,
		status: tc.success === false ? 'error' : 'completed',
		startedAt: now,
		completedAt: now,
		duration: 0
	}));

	completedTools.update((completed) => [...completed, ...entries]);
}

/** Clear all tool state (call at end of streaming). */
export function clearToolState(): void {
	activeTools.set([]);
	completedTools.set([]);
}
