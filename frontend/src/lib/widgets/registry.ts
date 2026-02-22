/**
 * Widget registry -- maps widget type strings to Svelte components.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { Component } from 'svelte';

import StatusBadge from '$lib/components/widgets/StatusBadge.svelte';
import EntityCard from '$lib/components/widgets/EntityCard.svelte';
import DataTable from '$lib/components/widgets/DataTable.svelte';
import ConfirmationCard from '$lib/components/widgets/ConfirmationCard.svelte';
import KeyValueList from '$lib/components/widgets/KeyValueList.svelte';
import AlertBanner from '$lib/components/widgets/AlertBanner.svelte';
import DiffViewer from '$lib/components/widgets/DiffViewer.svelte';
import Timeline from '$lib/components/widgets/Timeline.svelte';
import ExportCard from '$lib/components/widgets/ExportCard.svelte';

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const widgetRegistry: Record<string, Component> = {
	'status-badge': StatusBadge,
	'entity-card': EntityCard,
	'data-table': DataTable,
	'confirmation': ConfirmationCard,
	'key-value': KeyValueList,
	'alert': AlertBanner,
	'diff-viewer': DiffViewer,
	'timeline': Timeline,
	'export': ExportCard
};

// ---------------------------------------------------------------------------
// Lookup
// ---------------------------------------------------------------------------

/** Resolve a widget type string to its Svelte component, or undefined. */
export function getWidget(type: string): Component | undefined {
	return widgetRegistry[type];
}
