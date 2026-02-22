/**
 * Panel stores for the right-side detail panel stack.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { writable } from 'svelte/store';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PanelItem {
	id: string;
	widgetType: string;
	props: Record<string, unknown>;
	title: string;
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export const panelStack = writable<PanelItem[]>([]);
export const panelVisible = writable<boolean>(false);

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

/** Push a new item onto the panel stack and make the panel visible. */
export function pushPanel(item: PanelItem): void {
	panelStack.update((stack) => [...stack, item]);
	panelVisible.set(true);
}

/** Pop the top item from the panel stack. Hides the panel when empty. */
export function popPanel(): void {
	panelStack.update((stack) => {
		const next = stack.slice(0, -1);
		if (next.length === 0) {
			panelVisible.set(false);
		}
		return next;
	});
}

/** Close the panel entirely and clear the stack. */
export function closePanel(): void {
	panelStack.set([]);
	panelVisible.set(false);
}
